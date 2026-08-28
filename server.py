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
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
