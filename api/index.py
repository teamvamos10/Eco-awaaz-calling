from flask import Flask, request, jsonify, render_template
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from dotenv import load_dotenv

import os
import json
import traceback
import requests as http_requests
import psycopg2
from psycopg2.extras import RealDictCursor

from typing import Optional
from datetime import date, datetime, timedelta

load_dotenv(override=True)

import pathlib
_project_root = pathlib.Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    template_folder=str(_project_root / "templates"),
    static_folder=str(_project_root / "static"),
)


# -----------------------------
# Database Connection (Neon Postgres)
# -----------------------------
def get_neon_connection():
    db_url = (
        os.getenv("DATABASE_URL") or 
        os.getenv("NEON_DATABASE_URL") or 
        os.getenv("POSTGRES_URL") or ""
    ).strip()

    if not db_url or "your_neon_postgres_connection_string_here" in db_url:
        return None

    if not (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        return None

    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print("Neon Connection Error:", e)
        return None


def init_db():
    """Ensure the complaints_detail table schema matches in Neon PostgreSQL."""
    conn = get_neon_connection()
    if not conn:
        print("Notice: No Neon DATABASE_URL configured yet in .env")
        return

    try:
        with conn.cursor() as cur:
            # 1. Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS complaints_detail (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    postal_code VARCHAR(20),
                    address TEXT,
                    resource_type VARCHAR(50),
                    complaint_type VARCHAR(100),
                    description TEXT,
                    urgency_status VARCHAR(50),
                    severity VARCHAR(50),
                    phone_number VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'PENDING',
                    date DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 2. Migration for existing tables without gen_random_uuid() or urgency_status
            cur.execute("ALTER TABLE complaints_detail ADD COLUMN IF NOT EXISTS urgency_status VARCHAR(50);")
            cur.execute("ALTER TABLE complaints_detail ADD COLUMN IF NOT EXISTS severity VARCHAR(50);")
            cur.execute("ALTER TABLE complaints_detail ALTER COLUMN id SET DEFAULT gen_random_uuid();")
            cur.execute("ALTER TABLE complaints_detail ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;")
            cur.execute("ALTER TABLE complaints_detail ALTER COLUMN date SET DEFAULT CURRENT_DATE;")
            conn.commit()
        conn.close()
        print("Neon PostgreSQL initialized: table 'complaints_detail' is ready.")
    except Exception as e:
        print("Neon DB Init Notice:", e)


# Run schema setup on startup
init_db()


def required_env(*names):
    return [n for n in names if not os.getenv(n)]


@app.after_request
def add_cors_and_ngrok_headers(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    # CORS headers so the Vapi Web SDK proxy and API calls work from any origin
    origin = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.before_request
def strip_path_trailing_whitespace():
    """Strip %0A / trailing newlines from PATH_INFO before routing.
    Vercel can encode a trailing newline into the path which breaks route matching."""
    request.environ['PATH_INFO'] = request.environ.get('PATH_INFO', '').rstrip()


# -----------------------------
# Twilio Config
# -----------------------------
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
API_KEY = os.getenv("TWILIO_API_KEY")
API_SECRET = os.getenv("TWILIO_API_SECRET")
TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
@app.route("/api/index")
def index():
    return render_template("index.html")


@app.route("/api/vapi-config")
def vapi_config():
    """Return Vapi public key & assistant ID so the frontend can auto-connect."""
    load_dotenv(override=True)
    public_key = (os.getenv("VAPI_PUBLIC_KEY") or "").strip()
    assistant_id = (os.getenv("VAPI_ASSISTANT_ID") or "").strip()
    return jsonify({
        "publicKey": public_key,
        "assistantId": assistant_id,
    })


@app.route("/health")
def health():
    try:
        conn = get_neon_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM complaints_detail;")
                count = cur.fetchone()[0]
            conn.close()

            return jsonify({
                "status": "ok",
                "database": "connected (Neon PostgreSQL)",
                "total_complaints": count
            })

        return jsonify({
            "status": "warning",
            "message": "No database connection string configured (DATABASE_URL / NEON_DATABASE_URL)"
        }), 400

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "database error",
            "error": str(e)
        }), 500


@app.route("/token")
def token():
    missing = required_env(
        "TWILIO_ACCOUNT_SID",
        "TWILIO_API_KEY",
        "TWILIO_API_SECRET",
        "TWILIO_TWIML_APP_SID"
    )

    if missing:
        return jsonify({
            "error": "Missing Twilio configuration",
            "missing": missing
        }), 500

    access_token = AccessToken(
        ACCOUNT_SID,
        API_KEY,
        API_SECRET,
        identity="user"
    )

    voice_grant = VoiceGrant(
        outgoing_application_sid=TWIML_APP_SID,
        incoming_allow=True
    )

    access_token.add_grant(voice_grant)

    return jsonify({
        "token": access_token.to_jwt()
    })


# -----------------------------
# Webhook (Vapi Complaint Handler with Neon DB)
# -----------------------------
@app.route("/api/vapi-webhook", methods=["POST"])
def vapi_webhook():
    try:
        data = request.get_json(force=True)

        print("\n" + "=" * 70)
        print("WEBHOOK HIT:", datetime.now())
        print(json.dumps(data, indent=4))
        print("=" * 70)

        # Handle all Vapi tool payload structures
        if isinstance(data, dict):
            # Case 1: Wrapped in "query" JSON string
            if "query" in data and isinstance(data["query"], str):
                try:
                    data = json.loads(data["query"])
                except (TypeError, ValueError):
                    pass

            # Case 2: Vapi Server URL Webhook format
            if "message" in data and isinstance(data["message"], dict):
                msg = data["message"]
                # Subcase A: toolCalls array
                if "toolCalls" in msg and isinstance(msg["toolCalls"], list) and len(msg["toolCalls"]) > 0:
                    tool_call = msg["toolCalls"][0]
                    if "function" in tool_call and "arguments" in tool_call["function"]:
                        args = tool_call["function"]["arguments"]
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except: pass
                        if isinstance(args, dict):
                            data = args
                # Subcase B: toolWithToolCallList array
                elif "toolWithToolCallList" in msg and isinstance(msg["toolWithToolCallList"], list) and len(msg["toolWithToolCallList"]) > 0:
                    tc = msg["toolWithToolCallList"][0].get("toolCall", {})
                    if "function" in tc and "arguments" in tc["function"]:
                        args = tc["function"]["arguments"]
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except: pass
                        if isinstance(args, dict):
                            data = args
                # Subcase C: functionCall
                elif "functionCall" in msg and isinstance(msg["functionCall"], dict):
                    args = msg["functionCall"].get("parameters") or msg["functionCall"].get("arguments")
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: pass
                    if isinstance(args, dict):
                        data = args

        postal_code    = str(data.get("postal_code") or "").upper()
        address        = str(data.get("address") or "").upper()
        resource_type  = str(data.get("resource_type") or "").upper()
        complaint_type = str(data.get("complaint_type") or "").upper()
        description    = str(data.get("description") or "").upper()
        urgency_status = str(data.get("urgency_status") or data.get("severity") or "MEDIUM").upper()
        phone_number   = str(data.get("phone_number") or "")

        required_fields = {
            "postal_code": postal_code,
            "address": address,
            "resource_type": resource_type,
            "complaint_type": complaint_type,
        }
        missing_fields = [k for k, v in required_fields.items() if not v]

        if missing_fields:
            return jsonify({
                "success": False,
                "message": f"Missing required field(s): {', '.join(missing_fields)}"
            }), 400

        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        today_date = date.today().isoformat()

        # Connect to Neon PostgreSQL
        conn = get_neon_connection()
        
        if conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Duplicate check (last 2 days)
                cur.execute("""
                    SELECT id FROM complaints_detail
                    WHERE postal_code = %s
                      AND address = %s
                      AND resource_type = %s
                      AND complaint_type = %s
                      AND status = 'PENDING'
                      AND date >= %s
                    LIMIT 1;
                """, (str(postal_code), str(address), str(resource_type), str(complaint_type), two_days_ago))
                
                existing = cur.fetchone()

                if existing:
                    conn.close()
                    print(f"Duplicate complaint detected in Neon DB: ID {existing['id']}")
                    return jsonify({
                        "success": True,
                        "message": "Complaint already exists."
                    }), 200

                # 2. Insert new complaint
                print("\nSaving complaint to Neon PostgreSQL...")
                cur.execute("""
                    INSERT INTO complaints_detail 
                    (postal_code, address, resource_type, complaint_type, description, urgency_status, severity, phone_number, status, date, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', %s, CURRENT_TIMESTAMP)
                    RETURNING id;
                """, (
                    str(postal_code),
                    str(address),
                    str(resource_type),
                    str(complaint_type),
                    str(description or ""),
                    str(urgency_status),
                    str(urgency_status),
                    str(phone_number or ""),
                    today_date
                ))
                new_id = cur.fetchone()['id']
                conn.commit()

            conn.close()
            print(f"Complaint registered successfully in Neon DB with ID: {new_id}")

            return jsonify({
                "success": True,
                "message": "Complaint registered successfully.",
                "status": "completed",
                "complaint_id": str(new_id)
            }), 200

        return jsonify({
            "success": False,
            "message": "No database connection configured."
        }), 500

    except Exception as e:
        print("\n========== ERROR ==========")
        traceback.print_exc()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.errorhandler(404)
def page_not_found(e):
    """Debug 404 handler — shows what path Flask actually received."""
    return jsonify({
        "error": "404 Not Found",
        "flask_received_path": request.environ.get('PATH_INFO'),
        "request_url": request.url,
        "method": request.method,
        "x_matched_path": request.headers.get('x-matched-path', 'NOT SET'),
        "registered_routes": [str(rule) for rule in app.url_map.iter_rules()],
    }), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)