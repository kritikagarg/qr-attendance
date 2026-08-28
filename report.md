# Building a QR Code Attendance System with Google Sheets

A step-by-step guide to building a classroom attendance system where students scan a QR code, enter their name, and get marked present in a Google Sheet — automatically, from any device, on any network.

---

## What We're Building

The system has three moving parts:

1. **Admin page** — the instructor opens this, clicks "Start New Session", and a QR code is generated
2. **Student check-in page** — students scan the QR code on their phone, type their name, and get marked present
3. **Google Sheet** — the single source of truth; the app reads the roster from it and writes attendance back to it

The key feature is **fuzzy name matching** — students don't have to type their name perfectly. "alice s" will match "ALICE SMITH" in the roster. If a name genuinely doesn't match, the student sees a "Name not found" message and is asked to contact the instructor.

---

## Why These Technology Choices

| Choice | Why |
|--------|-----|
| **Python + Flask** | Simple web framework, great ecosystem for Google Sheets and fuzzy matching |
| **gspread** | Dead-simple Google Sheets wrapper — reading a column or writing a cell is 2-3 lines |
| **rapidfuzz** | Industry-standard fuzzy string matching library, handles typos and case differences reliably |
| **Render (free tier)** | Deploys a Python app from GitHub with zero config, gives a public HTTPS URL |
| **No database** | Google Sheet is both the roster and the attendance record — no extra infrastructure |

---

## Prerequisites

- Python 3.9+
- A Google account
- A Google Sheet with your student roster (see format below)
- A GitHub account
- A Render account (free at render.com)

---

## Google Sheet Format

The system expects this exact layout:

| Row | Column A | Column B onward |
|-----|----------|-----------------|
| 1 | *(instructions / blank)* | |
| 2 | Course name | Dates in `M/D` format (`8/26`, `9/2`, etc.) |
| 3 | `Student Names` | Day labels (`Mon`, `Wed`, etc.) |
| 4+ | Student names in ALL CAPS | `P` or `A` for attendance |

Example:

```
Row 1: [empty]
Row 2: CS_153 | 8/26 | 8/31 | 9/2 | ...
Row 3: Student Names | Wed | Mon | Wed | ...
Row 4: ALICE SMITH
Row 5: BOB JOHNSON
...
```

When a student checks in, the app writes `P` in the column matching today's date. If the date column doesn't exist in row 2, the app returns an error.

---

## Project Structure

```
qr-attendance/
├── server.py              # Flask entry point — routes + static file serving
├── state.py               # In-memory session storage (dict)
├── requirements.txt
├── render.yaml            # Render deployment config
├── .env.example
├── .gitignore
├── routes/
│   ├── admin.py           # POST /api/sessions, GET /api/sessions/<id>/attendance
│   └── attend.py          # POST /api/attend
├── services/
│   ├── sheets.py          # Google Sheets: read roster, write attendance
│   ├── matching.py        # Fuzzy name matching with rapidfuzz
│   └── qr.py              # QR code generation
└── public/
    ├── index.html         # Admin page (private — instructor only)
    ├── display.html       # Projector page (QR code only, no names)
    └── attend.html        # Student check-in page
```

---

## Step 1 — Set Up Google Cloud

The app authenticates with Google using a **service account** — a bot account that has been granted access to your specific spreadsheet.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (name it anything, e.g. `qr-attendance`)
3. In the search bar, search **"Google Sheets API"** → click Enable
4. Go to **IAM & Admin → Service Accounts** → **+ Create Service Account**
5. Give it a name (e.g. `qr-attendance`) → click **Create and Continue** → skip role fields → **Done**
6. Click on your new service account → go to **Keys** tab → **Add Key → Create new key → JSON** → download
7. Open the downloaded JSON and find `client_email` — it looks like `qr-attendance@your-project.iam.gserviceaccount.com`
8. **Share your Google Sheet** with that email address, giving it **Editor** access

> The service account only has access to files explicitly shared with it. It cannot access your Drive, Gmail, or any other sheet.

---

## Step 2 — Project Scaffold

```bash
mkdir qr-attendance && cd qr-attendance
mkdir routes services public
touch routes/__init__.py services/__init__.py
```

**`requirements.txt`:**
```
flask>=3.0.0
flask-cors>=4.0.0
gspread>=6.0.0
google-auth>=2.0.0
rapidfuzz>=3.0.0
qrcode[pil]>=7.0.0
python-dotenv>=1.0.0
gunicorn>=21.0.0
```

**`.env.example`:**
```
SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_CREDENTIALS_PATH=credentials.json   # for local dev
# GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}  # for production
BASE_URL=http://localhost:3000
PORT=3000
```

**`.gitignore`:**
```
.env
credentials.json
__pycache__/
*.pyc
venv/
```

> Find your `SPREADSHEET_ID` in the Google Sheets URL: `https://docs.google.com/spreadsheets/d/**<ID>**/edit`

---

## Step 3 — Session State

Sessions are kept in memory — no database needed. Each session tracks which students have checked in.

**`state.py`:**
```python
sessions = {}
# sessions[id] = {"date": "8/28", "checked_in": {row: {"name": str, "time": str}}}
```

---

## Step 4 — Google Sheets Service

**`services/sheets.py`** handles two things: reading the roster and writing attendance.

```python
import os, json
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

_client = None

def get_client():
    global _client
    if _client is not None:
        return _client
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
    if creds_json:
        creds_dict = json.loads(creds_json)
    else:
        with open(creds_path) as f:
            creds_dict = json.load(f)
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    _client = gspread.authorize(creds)
    return _client

def get_sheet():
    return get_client().open_by_key(os.getenv('SPREADSHEET_ID')).sheet1

def get_students():
    # Names start at row 4 (rows 1-3 are headers)
    col_a = get_sheet().col_values(1)
    return [{"name": name.strip(), "row": i}
            for i, name in enumerate(col_a[3:], start=4) if name.strip()]

def get_today_date_str():
    t = datetime.now()
    return f"{t.month}/{t.day}"  # "8/28" — no leading zeros, matches sheet format

def mark_present(row, date_str):
    sheet = get_sheet()
    date_row = sheet.row_values(2)  # row 2 has date headers
    col_index = next((i+1 for i, h in enumerate(date_row) if h.strip() == date_str), None)
    if col_index is None:
        raise ValueError(f"Date '{date_str}' not found in sheet")
    sheet.update_cell(row, col_index, 'P')
```

Key points:
- The client is cached after the first authentication call
- `get_students()` skips the first 3 rows (instructions, dates, header)
- `mark_present()` finds the date column dynamically — it doesn't assume a fixed column position
- Uses `"P"` to match the existing sheet convention

---

## Step 5 — Fuzzy Matching

**`services/matching.py`** normalizes both names to uppercase before comparing, so "john smith", "John Smith", and "JOHN SMITH" all match "JOHN SMITH" in the roster.

```python
from rapidfuzz import process, fuzz

SCORE_THRESHOLD = 70  # 0-100; 70 allows typos while blocking random names

def find_match(input_name, students):
    if not students:
        return {"noMatch": True}
    normalized = input_name.strip().upper()
    names = [s['name'] for s in students]
    best = process.extractOne(normalized, names, scorer=fuzz.WRatio, score_cutoff=SCORE_THRESHOLD)
    if best:
        name, score, idx = best
        return {"student": students[idx], "score": score}
    return {"noMatch": True}
```

`fuzz.WRatio` is a weighted ratio that handles partial matches, transpositions, and abbreviations well — it outperforms simple Levenshtein distance for name matching.

---

## Step 6 — QR Code Generation

**`services/qr.py`** generates a QR code in memory and returns it as a base64 data URL — no files written to disk.

```python
import base64, qrcode
from io import BytesIO

def generate_qr(url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64}"
```

---

## Step 7 — API Routes

**`routes/admin.py`** — creates sessions and returns attendance:

```python
import os, uuid
from flask import Blueprint, jsonify
from services.sheets import get_today_date_str
from services.qr import generate_qr
from state import sessions

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/sessions', methods=['POST'])
def create_session():
    session_id = str(uuid.uuid4())
    date_str = get_today_date_str()
    base_url = os.getenv('BASE_URL', 'http://localhost:3000').rstrip('/')
    attend_url = f"{base_url}/attend?session={session_id}"
    sessions[session_id] = {'date': date_str, 'checked_in': {}}
    return jsonify({'sessionId': session_id, 'qrDataUrl': generate_qr(attend_url), 'date': date_str})

@admin_bp.route('/api/sessions/<session_id>/attendance', methods=['GET'])
def get_attendance(session_id):
    session = sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    students = [{'name': v['name'], 'checkedInAt': v['time']}
                for v in session['checked_in'].values()]
    return jsonify({'students': students})
```

**`routes/attend.py`** — handles student check-ins:

```python
from datetime import datetime
from flask import Blueprint, jsonify, request
from services.sheets import get_students, mark_present
from services.matching import find_match
from state import sessions

attend_bp = Blueprint('attend', __name__)

@attend_bp.route('/api/attend', methods=['POST'])
def attend():
    data = request.get_json(silent=True) or {}
    session_id = data.get('sessionId', '').strip()
    input_name = data.get('name', '').strip()
    if not session_id or not input_name:
        return jsonify({'error': 'sessionId and name are required'}), 400
    session = sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    students = get_students()
    result = find_match(input_name, students)
    if 'noMatch' in result:
        return jsonify({'success': False, 'noMatch': True})
    student = result['student']
    if student['row'] in session['checked_in']:
        return jsonify({'success': False, 'alreadyCheckedIn': True, 'matchedName': student['name']})
    mark_present(student['row'], session['date'])
    session['checked_in'][student['row']] = {
        'name': student['name'], 'time': datetime.now().strftime('%I:%M %p')
    }
    return jsonify({'success': True, 'matchedName': student['name']})
```

---

## Step 8 — Flask App Entry Point

**`server.py`:**

```python
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from routes.admin import admin_bp
from routes.attend import attend_bp

app = Flask(__name__, static_folder='public')
CORS(app)
app.register_blueprint(admin_bp)
app.register_blueprint(attend_bp)

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/attend')
def attend_page():
    return send_from_directory('public', 'attend.html')

@app.route('/display')
def display_page():
    return send_from_directory('public', 'display.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 3000)), debug=True)
```

---

## Step 9 — Frontend Pages

Three HTML pages, all vanilla JS with no external dependencies:

### `public/index.html` — Admin (private)
- "Start New Session" button → calls `POST /api/sessions` → displays QR code
- "Project on Screen" button → opens `display.html` in a new tab (for the projector)
- Live attendance table — polls `GET /api/sessions/<id>/attendance` every 3 seconds
- Only the instructor sees this page

### `public/display.html` — Projector view (public)
- Dark background, large QR code
- Shows a live count of how many students have checked in
- No student names visible — safe to project in class

### `public/attend.html` — Student check-in (public)
- Simple name input form
- Shows one of four outcomes:
  - ✅ "Welcome, [Name]! You're marked present."
  - ⚠️ "You're already marked present today."
  - ❌ "Name not found. Please ask your instructor."
  - ❌ Error message if something went wrong

---

## Step 10 — Deploy to Render

**`render.yaml`:**
```yaml
services:
  - type: web
    name: qr-attendance
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn server:app --bind 0.0.0.0:$PORT
    envVars:
      - key: SPREADSHEET_ID
        sync: false
      - key: GOOGLE_CREDENTIALS_JSON
        sync: false
      - key: BASE_URL
        sync: false
```

**Deploy steps:**
1. Push code to GitHub
2. Go to render.com → New Web Service → connect your GitHub repo
3. Render auto-detects `render.yaml` — click Apply
4. In the **Environment** tab, set:
   - `SPREADSHEET_ID` — your sheet ID from the URL
   - `GOOGLE_CREDENTIALS_JSON` — paste the full contents of `credentials.json`
   - `BASE_URL` — leave blank until after first deploy
5. Deploy → once green, copy the URL (e.g. `https://your-app.onrender.com`)
6. Go back to Environment → set `BASE_URL` to that URL → Save (triggers redeploy)

> **Free tier note:** The app sleeps after 15 minutes of inactivity. Open the admin page ~2 minutes before class to wake it up.

---

## Running Locally

```bash
git clone https://github.com/your-username/qr-attendance.git
cd qr-attendance
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set GOOGLE_CREDENTIALS_PATH to your downloaded JSON key
python3 server.py
```

Open `http://localhost:3000`

---

## How to Use in Class

1. Open your Render URL ~2 minutes before class (wakes the server)
2. Click **Start New Session** — a QR code appears
3. Click **Project on Screen** — opens the projector view in a new tab
4. Put that tab on the projector — students scan it with their phones
5. Students type their name → marked present instantly in your Google Sheet
6. Your admin tab shows a live list of who has checked in
7. After class, open your Google Sheet — today's column is fully populated

---

## Security Notes

- `credentials.json` and `.env` are in `.gitignore` — they never touch GitHub
- The service account only has access to the one sheet you shared with it
- Render encrypts environment variables at rest
- The admin page has no authentication — add HTTP Basic Auth if you want to restrict access
- Student names are never shown to other students (the check-in page only shows the result for the current submission)
