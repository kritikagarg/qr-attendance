# QR Attendance System

A classroom attendance system where students scan a QR code, enter their name, and get marked present in a Google Sheet — automatically.

## How It Works

1. Instructor opens the admin page and clicks **Start New Session**
2. A QR code is generated for that session
3. Students scan the QR code on their phone (works on any network — no shared WiFi required)
4. Students type their name — the system fuzzy-matches it against the class roster
5. A **P** is written to today's date column in the Google Sheet instantly

Typos are handled gracefully. If a name doesn't match confidently, the student is shown the closest names to pick from.

## Tech Stack

- **Backend**: Python + Flask
- **Google Sheets**: `gspread` (reads roster, writes attendance)
- **Fuzzy matching**: `rapidfuzz` (tolerates name typos)
- **QR codes**: `qrcode` library
- **Deployment**: Render (free tier)

## Google Sheet Format

The system expects this layout:

| Row | Column A | Column B+ |
|-----|----------|-----------|
| 1 | *(instructions)* | |
| 2 | Course name | Dates as `M/D` (e.g. `8/28`) |
| 3 | `Student Names` | Day labels |
| 4+ | Student names (ALL CAPS) | `P` / `A` |

## Setup

### 1. Google Cloud (one-time)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a new project
2. Enable the **Google Sheets API**
3. Go to **IAM & Admin → Service Accounts** → create a service account → download the JSON key
4. Share your Google Sheet with the service account email (Editor access)

### 2. Local Development

```bash
git clone https://github.com/kritikagarg/qr-attendance.git
cd qr-attendance
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set GOOGLE_CREDENTIALS_PATH to your downloaded JSON key
python server.py
```

Open [http://localhost:3000](http://localhost:3000)

### 3. Deploy to Render

1. Connect this repo on [render.com](https://render.com) → New Web Service
2. Render will auto-detect `render.yaml`
3. Set these environment variables in the Render dashboard:

| Variable | Value |
|----------|-------|
| `SPREADSHEET_ID` | Your Google Sheet ID (from the URL) |
| `GOOGLE_CREDENTIALS_JSON` | Full contents of your service account JSON key |
| `BASE_URL` | Your Render URL (e.g. `https://qr-attendance-xxxx.onrender.com`) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SPREADSHEET_ID` | Google Sheet ID |
| `GOOGLE_CREDENTIALS_PATH` | Path to service account JSON (local dev) |
| `GOOGLE_CREDENTIALS_JSON` | Service account JSON as string (production) |
| `BASE_URL` | Public URL of the app (used in QR code links) |
| `PORT` | Port to run on (default: 3000) |
