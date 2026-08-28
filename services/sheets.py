import os
import json
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
    elif creds_path:
        with open(creds_path) as f:
            creds_dict = json.load(f)
    else:
        raise ValueError("Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_PATH in .env")

    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    _client = gspread.authorize(creds)
    return _client


def get_sheet():
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    return get_client().open_by_key(spreadsheet_id).sheet1


def get_students():
    """
    Returns list of {name, row} for all students.
    Sheet layout: row 1 = instructions, row 2 = dates, row 3 = "Student Names" header,
    row 4+ = actual student names in ALL CAPS in column A.
    """
    sheet = get_sheet()
    col_a = sheet.col_values(1)
    students = []
    for i, name in enumerate(col_a[3:], start=4):  # skip rows 1-3, use 1-indexed row numbers
        if name and name.strip():
            students.append({'name': name.strip(), 'row': i})
    return students


def get_today_date_str():
    today = datetime.now()
    return f"{today.month}/{today.day}"  # e.g. "8/28" — matches sheet format


def mark_present(row, date_str):
    """
    Finds the column in row 2 matching date_str (e.g. "8/28") and writes "P" at the given row.
    Raises ValueError if the date column is not found.
    """
    sheet = get_sheet()
    date_row = sheet.row_values(2)

    col_index = None
    for i, header in enumerate(date_row):
        if header.strip() == date_str:
            col_index = i + 1  # gspread uses 1-indexed columns
            break

    if col_index is None:
        available = [d for d in date_row if d and d != 'CS_153']
        raise ValueError(
            f"No column found for date '{date_str}'. "
            f"Available dates in sheet: {available[:10]}"
        )

    sheet.update_cell(row, col_index, 'P')
