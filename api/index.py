from flask import Flask, request, jsonify
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from dotenv import load_dotenv
import os
import json
import traceback
from datetime import date
from typing import Optional
from supabase import create_client, Client
from datetime import date, datetime, timedelta

load_dotenv()

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
 
supabase: Optional[Client] = None


def _required_env(*names: str) -> list[str]:
    return [name for name in names if not os.getenv(name)]


def _get_supabase() -> Client:
    global supabase
    if supabase is None:
        missing = _required_env("SUPABASE_URL", "SUPABASE_KEY")
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return supabase


@app.after_request
def skip_ngrok_warning(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
API_KEY = os.getenv("TWILIO_API_KEY")
API_SECRET = os.getenv("TWILIO_API_SECRET")


@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Eco-Awaaz Vapi Backend Running"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/token", methods=["GET"])
def token():
    missing = _required_env(
        "TWILIO_ACCOUNT_SID",
        "TWILIO_API_KEY",
        "TWILIO_API_SECRET",
        "TWILIO_TWIML_APP_SID",
    )
    if missing:
        return jsonify({
            "error": "Server is missing required Twilio configuration.",
            "missing": missing,
        }), 500

    access_token = AccessToken(ACCOUNT_SID, API_KEY, API_SECRET, identity="user")
    voice_grant = VoiceGrant(
        outgoing_application_sid=TWIML_APP_SID,
        incoming_allow=True
    )
    access_token.add_grant(voice_grant)
    return {"token": access_token.to_jwt()}

@app.route("/api/vapi-webhook", methods=["POST"])
def vapi_webhook():
    try:
        from datetime import datetime

        data = request.get_json(force=True)

        print("\n" + "=" * 70)
        print("WEBHOOK HIT:", datetime.now())
        print(json.dumps(data, indent=4))
        print("=" * 70)

        postal_code = data.get("postal_code")
        address = data.get("address")
        resource_type = data.get("resource_type")
        complaint_type = data.get("complaint_type")
        description = data.get("description")
        urgency_status = data.get("urgency_status")
        phone_number = data.get("phone_number", "Unknown")

        # Check for duplicate complaint
       two_days_ago = (date.today() - timedelta(days=2)).isoformat()

existing = (
    _get_supabase()
    .table("complaints_detail")
    .select("*")
    .eq("postal_code", postal_code)
    .eq("address", address)
    .eq("resource_type", resource_type)
    .eq("complaint_type", complaint_type)
    .eq("status", "PENDING")
    .gte("date", two_days_ago)
    .execute()
)

if existing.data:

    complaint = existing.data[0]

    current_count = complaint.get("report_count", 1)

    (
        _get_supabase()
        .table("complaints_detail")
        .update({
            "report_count": current_count + 1,
            "last_reported_at": datetime.now().isoformat()
        })
        .eq("id", complaint["id"])
        .execute()
    )

    print("Existing complaint updated.")
    print("Report Count:", current_count + 1)

    return jsonify({
        "success": True,
        "message": "Existing complaint updated."
    }), 200

        complaint = {
            "postal_code": postal_code,
            "address": address,
            "resource_type": resource_type,
            "complaint_type": complaint_type,
            "description": description,
            "urgency_status": urgency_status,
            "phone_number": phone_number,
            "status": "PENDING",
            "date": date.today().isoformat()
        }

        print("\nSaving complaint...")
        print(json.dumps(complaint, indent=4))

        result = (
            _get_supabase()
            .table("complaints_detail")
            .insert(complaint)
            .execute()
        )

        print("Complaint saved successfully.")
        print(result)

        return jsonify({
            "success": True,
            "message": "Complaint registered successfully."
        }), 200

    except Exception as e:
        print("\n========== ERROR ==========")
        traceback.print_exc()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)

