# VoteSmart — Election Education Platform
## Python Backend Setup Guide

---

## 📁 Project Structure

```
votesmart-backend/
├── main.py              ← FastAPI backend (Python)
├── requirements.txt     ← Python dependencies
├── votesmart.db         ← SQLite database (auto-created on first run)
└── static/
    └── index.html       ← Frontend (served by backend)
```

---

## 🚀 Setup & Run (3 Steps)

### Step 1 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Start the Backend
```bash
uvicorn main:app --reload --port 8000
```

### Step 3 — Open the App
Visit: **http://localhost:8000**

---

## 🔑 Demo Login
- **Email:** demo@votesmart.edu
- **Password:** demo123

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register | Create new account |
| POST | /api/auth/login | Login & get token |
| POST | /api/auth/logout | Logout |
| GET | /api/auth/me | Get current user |
| POST | /api/chat | Send message to CivicBot AI |
| GET | /api/chat/history | Get chat history |
| POST | /api/quiz/result | Save quiz score |
| GET | /api/quiz/leaderboard | Get top scores |
| GET | /api/quiz/my-results | Get my quiz history |
| GET | /api/progress | Get user progress |
| GET | /api/stats | Platform-wide stats |

📖 Auto-generated API docs: **http://localhost:8000/docs**

---

## 🗄️ Database Tables
- **users** — Registered user accounts
- **sessions** — Auth tokens (7-day expiry)
- **chat_history** — All AI conversations
- **quiz_results** — Quiz scores per user
- **user_progress** — Points, topic count, stats

---

## 🌐 Deploy to a Public Server

### Option A — Railway (Free)
1. Push project to GitHub
2. Go to railway.app → New Project → Deploy from GitHub
3. Railway auto-detects Python and runs uvicorn
4. Get a public URL like: https://votesmart.up.railway.app

### Option B — Render (Free)
1. Go to render.com → New Web Service
2. Connect GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Option C — Run Locally + Share with ngrok
```bash
# Install ngrok from ngrok.com, then:
ngrok http 8000
# You get a public URL like: https://abc123.ngrok.io
```

---

Built with FastAPI + SQLite + Python 🐍
