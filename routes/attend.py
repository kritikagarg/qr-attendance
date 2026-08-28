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
        return jsonify({'error': 'Session not found or expired'}), 404

    try:
        students = get_students()
    except Exception as e:
        return jsonify({'error': f'Could not read roster: {e}'}), 500

    result = find_match(input_name, students)

    if 'noMatch' in result:
        return jsonify({'success': False, 'noMatch': True})

    if 'suggestions' in result:
        return jsonify({'success': False, 'noMatch': True})

    student = result['student']
    row = student['row']
    matched_name = student['name']

    if row in session['checked_in']:
        return jsonify({'success': False, 'alreadyCheckedIn': True, 'matchedName': matched_name})

    try:
        mark_present(row, session['date'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Could not update sheet: {e}'}), 500

    now = datetime.now().strftime('%I:%M %p')
    session['checked_in'][row] = {'name': matched_name, 'time': now}

    return jsonify({'success': True, 'matchedName': matched_name})
