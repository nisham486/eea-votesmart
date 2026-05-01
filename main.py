"""
VoteSmart Election Education Platform
Python FastAPI Backend
Run: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import sqlite3
import hashlib
import secrets
import json
import os
import time
from datetime import datetime

# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────
app = FastAPI(
    title="VoteSmart API",
    description="Backend for the Election Education Platform",
    version="1.0.0"
)

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# DATABASE SETUP (SQLite)
# ─────────────────────────────────────────
DB_PATH = "votesmart.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'citizen',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    """)

    # Sessions table (token-based auth)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Quiz results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            quiz_type TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            percentage REAL NOT NULL,
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Chat history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Progress tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            topics_completed INTEGER DEFAULT 0,
            chat_count INTEGER DEFAULT 0,
            quiz_count INTEGER DEFAULT 0,
            total_points INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Insert demo user
    demo_hash = hash_password("demo123")
    cursor.execute("""
        INSERT OR IGNORE INTO users (first_name, last_name, email, password_hash, role)
        VALUES (?, ?, ?, ?, ?)
    """, ("Alex", "Johnson", "demo@votesmart.edu", demo_hash, "student"))

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token() -> str:
    return secrets.token_hex(32)

def get_user_from_token(token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > datetime('now')
    """, (token,))
    user = cursor.fetchone()
    conn.close()
    return user

# ─────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────
class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    role: Optional[str] = "citizen"

class LoginRequest(BaseModel):
    email: str
    password: str

class ChatMessage(BaseModel):
    message: str
    token: str

class QuizResult(BaseModel):
    token: str
    quiz_type: str
    score: int
    total: int

class ProgressUpdate(BaseModel):
    token: str
    action: str  # "chat", "quiz", "topic"

# ─────────────────────────────────────────
# CIVICBOT AI ENGINE
# ─────────────────────────────────────────
CIVICBOT_RESPONSES = {
    "greetings": {
        "triggers": ["hello", "hi", "hey", "good morning", "good evening", "howdy", "greetings"],
        "response": "Hello! 👋 Welcome to **CivicBot**, your election education guide!\n\nI can help you understand:\n• How elections work in the USA\n• Voter registration & your rights\n• The Electoral College system\n• Political parties & primaries\n• Voting history & milestones\n\nWhat would you like to learn today?"
    },
    "register": {
        "triggers": ["register", "registration", "sign up to vote", "how do i vote", "eligible"],
        "response": "**How to Register to Vote** ✅\n\nRegistering is quick and free!\n\n**Online:** Visit vote.gov — the official federal site.\n\n**By Mail:** Download your state's form and mail it to your local election office.\n\n**In Person:** Visit your DMV, library, or election office.\n\n**Requirements:**\n• U.S. citizen\n• At least 18 years old on Election Day\n• Meet your state's residency requirement\n\n**Deadlines:** Most states require registration 15–30 days before an election. Some offer same-day registration!"
    },
    "electoral_college": {
        "triggers": ["electoral college", "electors", "electoral vote", "270", "swing state"],
        "response": "**The Electoral College** 🏛️\n\nThe U.S. uses the Electoral College — not a direct popular vote — to elect the President!\n\n**How It Works:**\n1. Each state gets electoral votes = House seats + 2 senators\n2. Most states use winner-take-all\n3. There are 538 total electoral votes\n4. A candidate needs **270+ to win**\n\n**Why Does It Exist?**\nThe Founders created it in 1787 as a compromise between small and large states.\n\n**Swing States:** States like Pennsylvania, Michigan, Arizona are highly contested!"
    },
    "gerrymandering": {
        "triggers": ["gerrymander", "gerrymandering", "redistrict", "district lines"],
        "response": "**Gerrymandering** 🗺️\n\nGerrymandering is when district boundaries are *deliberately drawn* to give one party an unfair advantage.\n\n**Two Main Techniques:**\n🔴 **Packing** — Cramming opposition voters into one district\n🔵 **Cracking** — Splitting opposition voters across many districts\n\n**Who Draws the Maps?**\nIn most states, the state legislature draws lines after each Census (every 10 years).\n\n**Reforms:** Independent commissions (used in CA, AZ, MI) aim to create fairer maps."
    },
    "voting_rights": {
        "triggers": ["voting rights", "right to vote", "15th amendment", "19th amendment", "26th amendment", "suffrage"],
        "response": "**Voting Rights in America** ✊\n\n**Key Milestones:**\n• **1870 — 15th Amendment:** Cannot deny vote based on race\n• **1920 — 19th Amendment:** Women's right to vote\n• **1965 — Voting Rights Act:** Banned literacy tests and discriminatory practices\n• **1971 — 26th Amendment:** Voting age lowered to 18\n\n**Your Rights at the Polls:**\n• If you're in line when polls close, you have the RIGHT to vote\n• You can request a provisional ballot\n• No one can intimidate or coerce you"
    },
    "primary": {
        "triggers": ["primary", "caucus", "nomination", "party candidate"],
        "response": "**Primaries & Caucuses** 🏁\n\nBefore the general election, each party picks its candidate.\n\n**Primary Elections:** Voters cast secret ballots. Types include:\n• **Open Primary:** Any registered voter can participate\n• **Closed Primary:** Only party members can vote\n\n**Caucuses:** Voters physically gather, debate, and vote publicly.\n\n**Super Tuesday:** A single day when many states hold primaries — often determines the nominee!\n\n**Delegates:** Winners earn delegates who formally nominate the candidate at the national convention."
    },
    "ranked_choice": {
        "triggers": ["ranked choice", "rcv", "instant runoff", "rank candidates"],
        "response": "**Ranked Choice Voting (RCV)** 🔢\n\nInstead of picking ONE candidate, you rank them 1st, 2nd, 3rd...\n\n**How It's Counted:**\n1. Count 1st-choice votes\n2. If someone has 50%+ → they win!\n3. If not, eliminate last-place candidate\n4. Transfer their votes to 2nd choices\n5. Repeat until someone wins\n\n**Benefits:** ✅ Eliminates spoiler effect ✅ Encourages broad appeal\n\n**Used in:** Maine, Alaska (federal), NYC (local primaries)"
    },
    "campaign_finance": {
        "triggers": ["campaign finance", "super pac", "dark money", "citizens united", "donation", "pac"],
        "response": "**Campaign Finance** 💰\n\n**Individual Contributions:** Up to $3,300 per candidate per election (2024 limit)\n\n**Super PACs:** Can raise *unlimited* money but cannot coordinate directly with campaigns\n\n**Dark Money:** Nonprofits that spend on elections without disclosing donors\n\n**Citizens United (2010):** Supreme Court ruled corporate political spending is protected free speech — opened the floodgates for outside spending\n\nTotal 2020 election spending exceeded **$14 billion**!"
    },
    "congress": {
        "triggers": ["congress", "senate", "house", "representative", "senator", "legislature"],
        "response": "**The U.S. Congress** 🏛️\n\n**Senate (100 members):**\n• 2 per state regardless of population\n• 6-year terms, must be 30+\n• Special powers: Ratify treaties, confirm nominations\n\n**House (435 members):**\n• Allocated by state population\n• 2-year terms, must be 25+\n• All revenue bills originate here\n\n**How a Bill Becomes Law:**\n1. Introduced → Committee review\n2. Full chamber vote\n3. Other chamber repeats\n4. President signs or vetoes\n5. Congress can override with 2/3 vote"
    },
    "types_elections": {
        "triggers": ["types of election", "kinds of election", "midterm", "local election", "special election"],
        "response": "**Types of U.S. Elections** 🗳️\n\n**Federal:**\n• Presidential — Every 4 years\n• Senate — 1/3 of seats every 2 years\n• House — ALL 435 seats every 2 years\n\n**Midterm Elections:** Held 2 years into presidential term — president's party historically loses seats\n\n**State Elections:** Governors, state legislators, attorneys general\n\n**Local Elections:** Mayors, city councils, school boards — often held in odd years with very low turnout!\n\n**Special Elections:** Fill vacancies outside the regular schedule"
    },
    "history": {
        "triggers": ["election history", "historical", "famous election", "2000 election", "landmark"],
        "response": "**Landmark U.S. Elections** 📚\n\n**1800:** First peaceful transfer of power between opposing parties\n\n**1860:** Lincoln won without a single Southern state → triggered the Civil War\n\n**1920:** Women voted in a presidential election for the first time\n\n**1965:** Voting Rights Act outlawed discriminatory voting practices\n\n**2000 — Bush v. Gore:** Decided by 537 votes in Florida; Supreme Court stopped the recount\n\n**2008:** Barack Obama became the first African American President"
    },
    "help": {
        "triggers": ["help", "what can you do", "topics", "menu"],
        "response": "I'm CivicBot — here to help with all things elections! 🗳️\n\nAsk me about:\n• **Voter registration** — how to sign up\n• **Electoral College** — how it works\n• **Types of elections** — primaries, general, local\n• **Voting rights** — history and current issues\n• **Gerrymandering** — and redistricting\n• **Campaign finance** — PACs, Super PACs, dark money\n• **Ranked choice voting** — alternative systems\n• **Congress** — Senate vs House\n• **Election history** — famous elections\n\nJust type your question!"
    }
}

def get_civicbot_response(message: str) -> str:
    msg = message.lower().strip()

    for topic, data in CIVICBOT_RESPONSES.items():
        if any(trigger in msg for trigger in data["triggers"]):
            return data["response"]

    # Smart fallback responses
    if "thank" in msg:
        return "You're very welcome! 😊 Civic knowledge is power. Is there anything else about elections you'd like to explore?"
    if "why" in msg and "vote" in msg:
        return "**Why Does Voting Matter?** 🗳️\n\nYour vote is your voice in a democracy!\n\n• Local elections are often decided by just dozens of votes\n• Policies affecting your daily life are determined by elected officials\n• People fought and died for the right to vote\n\nIn 2020, about **33% of eligible voters** did NOT vote. Every vote genuinely shifts outcomes!"
    if "how many" in msg or "number" in msg:
        return "Key election numbers to know! 🔢\n\n• **538** total Electoral College votes\n• **270** needed to win presidency\n• **100** U.S. Senators\n• **435** House members\n• **18** minimum voting age\n• **4 years** presidential term\n• **2 terms** presidential limit"

    return f"Great civic question! 🏛️ I can help with:\n\n• **Voter registration** — type 'register'\n• **Electoral College** — type 'electoral college'\n• **Voting rights** — type 'voting rights'\n• **Election types** — type 'types of elections'\n• **Gerrymandering** — type 'gerrymandering'\n• **Campaign finance** — type 'super pac'\n\nCould you rephrase your question? I'm here to help! 😊"

# ─────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/api")
def api_info():
    return {
        "name": "VoteSmart API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "POST /api/auth/register",
            "POST /api/auth/login",
            "POST /api/auth/logout",
            "GET  /api/auth/me",
            "POST /api/chat",
            "GET  /api/chat/history",
            "POST /api/quiz/result",
            "GET  /api/quiz/leaderboard",
            "GET  /api/progress",
            "POST /api/progress/update",
        ]
    }

# ── AUTH ROUTES ──────────────────────────

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    conn = get_db()
    cursor = conn.cursor()

    # Check if email exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (req.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create user
    password_hash = hash_password(req.password)
    cursor.execute("""
        INSERT INTO users (first_name, last_name, email, password_hash, role)
        VALUES (?, ?, ?, ?, ?)
    """, (req.first_name, req.last_name, req.email, password_hash, req.role))

    user_id = cursor.lastrowid

    # Initialize progress
    cursor.execute("""
        INSERT INTO user_progress (user_id) VALUES (?)
    """, (user_id,))

    # Create session token
    token = generate_token()
    cursor.execute("""
        INSERT INTO sessions (user_id, token, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
    """, (user_id, token))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user_id,
            "first_name": req.first_name,
            "last_name": req.last_name,
            "email": req.email,
            "role": req.role
        }
    }


@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = get_db()
    cursor = conn.cursor()

    password_hash = hash_password(req.password)
    cursor.execute("""
        SELECT * FROM users WHERE email = ? AND password_hash = ?
    """, (req.email, password_hash))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last login
    cursor.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (user["id"],))

    # Create new session token
    token = generate_token()
    cursor.execute("""
        INSERT INTO sessions (user_id, token, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
    """, (user["id"], token))

    # Ensure progress row exists
    cursor.execute("""
        INSERT OR IGNORE INTO user_progress (user_id) VALUES (?)
    """, (user["id"],))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"],
            "role": user["role"]
        }
    }


@app.post("/api/auth/logout")
def logout(token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Logged out successfully"}


@app.get("/api/auth/me")
def get_me(token: str):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {
        "id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"],
        "role": user["role"],
        "created_at": user["created_at"]
    }

# ── CHAT ROUTES ──────────────────────────

@app.post("/api/chat")
def chat(req: ChatMessage):
    user = get_user_from_token(req.token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Get AI response
    response = get_civicbot_response(req.message)

    # Save both messages to history
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_history (user_id, role, message) VALUES (?, 'user', ?)
    """, (user["id"], req.message))
    cursor.execute("""
        INSERT INTO chat_history (user_id, role, message) VALUES (?, 'assistant', ?)
    """, (user["id"], response))

    # Update chat count in progress
    cursor.execute("""
        UPDATE user_progress
        SET chat_count = chat_count + 1,
            total_points = total_points + 2,
            updated_at = datetime('now')
        WHERE user_id = ?
    """, (user["id"],))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "response": response,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/chat/history")
def get_chat_history(token: str, limit: int = 50):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, message, timestamp
        FROM chat_history
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (user["id"], limit))
    rows = cursor.fetchall()
    conn.close()

    return {
        "history": [
            {"role": r["role"], "message": r["message"], "timestamp": r["timestamp"]}
            for r in reversed(rows)
        ]
    }

# ── QUIZ ROUTES ──────────────────────────

@app.post("/api/quiz/result")
def save_quiz_result(req: QuizResult):
    user = get_user_from_token(req.token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    percentage = round((req.score / req.total) * 100, 1)
    points = req.score * 10

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO quiz_results (user_id, quiz_type, score, total, percentage)
        VALUES (?, ?, ?, ?, ?)
    """, (user["id"], req.quiz_type, req.score, req.total, percentage))

    # Update progress
    cursor.execute("""
        UPDATE user_progress
        SET quiz_count = quiz_count + 1,
            total_points = total_points + ?,
            updated_at = datetime('now')
        WHERE user_id = ?
    """, (points, user["id"]))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "percentage": percentage,
        "points_earned": points,
        "message": "Quiz result saved!"
    }


@app.get("/api/quiz/leaderboard")
def get_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.first_name, u.last_name,
               MAX(qr.percentage) as best_score,
               COUNT(qr.id) as quizzes_taken,
               up.total_points
        FROM users u
        JOIN quiz_results qr ON u.id = qr.user_id
        JOIN user_progress up ON u.id = up.user_id
        GROUP BY u.id
        ORDER BY up.total_points DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    return {
        "leaderboard": [
            {
                "name": f"{r['first_name']} {r['last_name']}",
                "best_score": r["best_score"],
                "quizzes_taken": r["quizzes_taken"],
                "total_points": r["total_points"]
            }
            for r in rows
        ]
    }


@app.get("/api/quiz/my-results")
def get_my_results(token: str):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT quiz_type, score, total, percentage, completed_at
        FROM quiz_results
        WHERE user_id = ?
        ORDER BY completed_at DESC
    """, (user["id"],))
    rows = cursor.fetchall()
    conn.close()

    return {
        "results": [dict(r) for r in rows]
    }

# ── PROGRESS ROUTES ──────────────────────

@app.get("/api/progress")
def get_progress(token: str):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_progress WHERE user_id = ?", (user["id"],))
    progress = cursor.fetchone()

    # Get best quiz score
    cursor.execute("""
        SELECT MAX(percentage) as best FROM quiz_results WHERE user_id = ?
    """, (user["id"],))
    best = cursor.fetchone()

    conn.close()

    if not progress:
        return {"topics_completed": 0, "chat_count": 0, "quiz_count": 0, "total_points": 0, "best_score": None}

    return {
        "topics_completed": progress["topics_completed"],
        "chat_count": progress["chat_count"],
        "quiz_count": progress["quiz_count"],
        "total_points": progress["total_points"],
        "best_score": best["best"] if best else None
    }


@app.get("/api/stats")
def get_platform_stats():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM users")
    users_count = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as total FROM quiz_results")
    quizzes_count = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as total FROM chat_history WHERE role='user'")
    chats_count = cursor.fetchone()["total"]
    conn.close()

    return {
        "total_users": users_count,
        "total_quizzes_taken": quizzes_count,
        "total_chat_messages": chats_count,
        "platform": "VoteSmart Election Education"
    }

# ─────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
