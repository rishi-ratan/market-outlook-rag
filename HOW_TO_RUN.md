# 🚀 How to Run - Simple Instructions

## Step 1: Check Your Setup

Make sure you have:
- ✅ Python installed
- ✅ Node.js installed
- ✅ `.env` file with your `OPENAI_API_KEY`

---

## Step 2: Start Backend (Terminal 1)

Open a terminal/PowerShell and run:

```bash
cd market-outlook-rag
uvicorn apps.api.main:app --reload --port 8000
```

**OR** if you have a virtual environment:
```bash
cd market-outlook-rag
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Mac/Linux

uvicorn apps.api.main:app --reload --port 8000
```

Wait until you see: `INFO: Uvicorn running on http://0.0.0.0:8000`

**Keep this terminal open!**

---

## Step 3: Start Frontend (Terminal 2)

Open a **NEW terminal** and run:

```bash
cd market-outlook-rag\apps\web
npm install  # First time only
npm run dev
```

Wait until you see: `✓ Ready` and `Local: http://localhost:3000`

**Keep this terminal open!**

---

## Step 4: Open Browser

Go to: **http://localhost:3000**

---

## ✅ That's It!

You should now see the Market Outlook Analyst interface.

---

## 🐛 Troubleshooting

### "uvicorn: command not found"
Install it:
```bash
pip install uvicorn fastapi
```

### "npm: command not found"
Install Node.js from: https://nodejs.org/

### "Missing OPENAI_API_KEY"
Create `.env` file in `market-outlook-rag` folder:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

### Port 8000 or 3000 already in use
Kill the process using that port, or use different ports:
```bash
# Backend on 8001
uvicorn apps.api.main:app --reload --port 8001

# Frontend on 3001
npm run dev -- -p 3001
```

---

## 📝 Quick Commands Summary

**Terminal 1:**
```bash
cd market-outlook-rag
uvicorn apps.api.main:app --reload --port 8000
```

**Terminal 2:**
```bash
cd market-outlook-rag\apps\web
npm run dev
```

**Browser:**
http://localhost:3000
