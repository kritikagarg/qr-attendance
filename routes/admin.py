import os
import uuid
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

    qr_data_url = generate_qr(attend_url)

    sessions[session_id] = {
        'date': date_str,
        'checked_in': {}  # row -> {name, time}
    }

    return jsonify({
        'sessionId': session_id,
        'qrDataUrl': qr_data_url,
        'date': date_str,
        'attendUrl': attend_url,
    })


@admin_bp.route('/api/sessions/<session_id>/attendance', methods=['GET'])
def get_attendance(session_id):
    session = sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    students = [
        {'name': info['name'], 'checkedInAt': info['time']}
        for info in session['checked_in'].values()
    ]

    return jsonify({'students': students})
