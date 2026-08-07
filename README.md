# 🌿 Eco-Awaaz — AI-Powered Civic Complaint Platform

Eco-Awaaz is an intelligent civic calling platform designed to turn telephone and web-based voice signals into structured, actionable municipal response tickets. Citizens can report civic issues (Water supply, Electricity outages, Waste management) in their native regional languages simply by speaking. The AI automatically registers, geolocates (via postal PIN), prioritizes, and logs complaints into a secure Neon PostgreSQL database in real-time.

---

## 🚀 Key Features

*   **Multilingual AI Voice Assistant**: Natural voice conversation in English, Hindi, Marathi, and Kannada. Automatically detects the language and responds back in the same tongue.
*   **Zero App/Internet Requirement**: Works directly over standard telephone lines (via Twilio/Vapi) or via the WebRTC browser dialer.
*   **Automatic Complaint Registration**: Parses voice input, categorizes resources, extracts location coordinates (6-digit PIN code), and maps severity/urgency without form entry.
*   **Neon Serverless PostgreSQL Storage**: Secure, fast, and modern relational database backend.
*   **2-Day Smart Duplicate Check**: Prevents municipal overloading by automatically filtering duplicate complaints from the same address and resource type within a rolling 48-hour window.
*   **Vercel-Optimized Deployment**: Ready to launch as a serverless Flask app.

---

## 🛠️ Technology Stack

*   **Backend**: Flask (Python 3.12), Twilio Voice SDK, Vapi API, `psycopg2`
*   **Frontend**: HTML5, Vanilla CSS System (Variables, Custom Animations), ES6 JavaScript (using Vapi Web SDK ESM build)
*   **Database**: Neon Serverless PostgreSQL

---

## 📦 Project Structure

```
eco-awaaz-call/
├── api/
│   └── index.py         # Flask app routes (token endpoint, config, Vapi webhook)
├── templates/
│   └── index.html       # Redesigned calling dashboard (Command Center Theme)
├── static/
│   ├── css/
│   │   └── style.css    # Clean global theme styling
│   └── js/
│       └── app.js       # Core frontend logic for browser client
├── vercel.json          # Vercel deployment & rewrite configuration
├── requirements.txt     # Python production dependencies
└── .env                 # Server connection credentials (ignored in Git)
```

---

## 🔑 Environment Variables Setup

Create a `.env` file in the root directory and populate it with the following credentials:

```env
# Twilio Voice Credentials
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_TWIML_APP_SID=your_twilio_twiml_app_sid
TWILIO_NUMBER=your_twilio_phone_number
TWILIO_API_KEY=your_twilio_api_key
TWILIO_API_SECRET=your_twilio_api_secret

# Vapi Web SDK Credentials
VAPI_PRIVATE_KEY=your_vapi_private_key
VAPI_PUBLIC_KEY=your_vapi_public_key
VAPI_ASSISTANT_ID=your_vapi_assistant_id

# Neon PostgreSQL Database Connection String
DATABASE_URL=postgresql://user:password@ep-xyz.ap-southeast-1.aws.neon.tech/ecoawaaz?sslmode=require
```

---

## ⚙️ Local Development Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/teamvamos10/Eco-awaaz-calling.git
    cd Eco-awaaz-calling
    ```

2.  **Create and Activate Virtual Environment**:
    ```bash
    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # macOS/Linux:
    source .venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Server**:
    ```bash
    python api/index.py
    ```
    Your application will be live at `http://localhost:5000`.

---

## ☁️ Deployment to Vercel

This repository is pre-configured with a `vercel.json` rewrite file to support seamless serverless deployment.

1.  **Connect GitHub to Vercel**:
    *   Log in to [Vercel Dashboard](https://vercel.com).
    *   Click **Add New Project** and select your imported GitHub repository.
2.  **Add Environment Variables**:
    *   Under **Project Settings** -> **Environment Variables**, copy-paste all keys from your local `.env` file.
3.  **Deploy**:
    *   Click **Deploy**. Vercel will build the serverless functions and serve your front-end instantly.

---

## 📊 End-To-End System Pipeline

```
[ Citizen Call ] 📞 
       ↓
[ Voice Input ] (Regional Language Speech) 🗣️
       ↓
[ Verification ] (Duplicate check & Address validation) 🛡️
       ↓
[ AI Classification ] (Categorized to Water/Electricity/Waste) 🧠
       ↓
[ Location Extraction ] (PIN Code verification) 📍
       ↓
[ Priority Scoring ] (Severity mapped to Critical/High/Medium/Low) ⚠️
       ↓
[ Secure Log ] (Saved to Neon Serverless PostgreSQL) 🐘
       ↓
[ Smart Dispatch ] (Forwarded to Municipal Action team) 🚛
```
