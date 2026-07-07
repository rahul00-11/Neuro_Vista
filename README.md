# NeuroVista AI v2.0
**Clinician-Led Digital Health Platform for Pediatric Neuro-Ophthalmology**
Dr. Trupti Kadam Lambat — Little Angels Superspecialty Eye Clinic, Nagpur

---

## 📁 Structure
```
neurovista_final/
├── backend/
│   ├── main.py              ← FastAPI app (also serves frontend)
│   ├── config.py            ← Reads .env
│   ├── requirements.txt
│   ├── .env.example         ← Copy to .env
│   ├── models/
│   │   ├── database.py      ← SQLite, all 6 agent tables
│   │   ├── ai_engine.py     ← Groq API, 6 agent prompts
│   │   └── language_utils.py
│   └── routers/
│       ├── patients.py      ← /api/patients/*
│       └── files.py         ← /api/files/upload/*
│
├── frontend/
│   ├── index.html           ← Mobile-first UI with welcome screen
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js       ← All 6 agent flows
│           ├── api.js       ← Backend client
│           └── voice.js     ← Web Speech API
│
├── render.yaml              ← One-click Render deployment
└── .gitignore
```

---

## 🤖 Layer 1 Agents (6 modules)
| # | Agent | Purpose |
|---|-------|---------|
| 1 | Registration Agent | Collect child + guardian details (age 0–18 enforced) |
| 2 | Consent Agent | Data, photo, research consent |
| 3 | History Collection Agent | Birth history, milestones, chief complaint |
| 4 | Symptom Checker Agent | Neuro-ophthalmic symptom screening |
| 5 | Appointment Agent | Schedule/confirm visit |
| 6 | Caregiver Education Agent | Eye health tips for parents |

---

## ⚡ Local Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env → add your GROQ_API_KEY from console.groq.com
python main.py
# Open: http://localhost:8000
```

---

## 🚀 Deploy to Render (Free)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "NeuroVista AI v2.0"
git remote add origin https://github.com/rahul00-11/neurovista-ai.git
git push -u origin main
```

### Step 2 — Render setup
1. Go to **render.com** → New → **Web Service**
2. Connect your GitHub repo
3. Render auto-detects `render.yaml`
4. Go to **Environment** tab → Add: `GROQ_API_KEY = gsk_your_key`
5. Click **Deploy**

### Step 3 — Done!
Your app runs at: `https://neurovista-ai.onrender.com`

> **Note:** Render free tier sleeps after 15min inactivity — first load takes ~30s to wake up.

---

## 🔐 Security
- Groq API key never leaves the server
- SQLite stored on Render's persistent disk
- Age validation: 0–18 only (enforced in Pydantic + server)
- CORS: open for now (tighten in production)

---

## 📱 Mobile Features
- Responsive mobile-first design
- Works on iOS Safari + Android Chrome
- Voice input (Chrome/Edge required for SpeechRecognition)
- Bottom sheet for patient info + uploads on mobile
- `viewport-fit=cover` for safe area on notched phones
