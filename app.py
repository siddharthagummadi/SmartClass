from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
import mysql.connector
import random
import string
import time
import base64
import numpy as np
import cv2
import pandas as pd
import io
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

app = Flask(__name__)
# Secure secret key for production
app.secret_key = os.getenv('SECRET_KEY', 'default_development_key_change_me')

# DATA_DIR: Use /data for Render persistence, or 'data' for local dev
BASE_DIR = os.getenv("DATA_DIR", "data")
FACE_DATA_DIR = os.path.join(BASE_DIR, "face_data")
TRAINER_PATH = os.path.join(BASE_DIR, "trainer.yml")

os.makedirs(FACE_DATA_DIR, exist_ok=True)

def get_db():
    host = os.getenv('MYSQL_HOST') or os.getenv('MYSQLHOST') or 'localhost'
    user = os.getenv('MYSQL_USER') or os.getenv('MYSQLUSER') or 'root'
    password = os.getenv('MYSQL_PASSWORD') or os.getenv('MYSQLPASSWORD') or '1605'
    database = os.getenv('MYSQL_DATABASE') or os.getenv('MYSQLDATABASE') or 'smartclass'
    port = int(os.getenv('MYSQL_PORT') or os.getenv('MYSQLPORT') or 3306)

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port
    )

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('role') != role:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def home():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif role == 'student':
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return "ok", 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            db = get_db()
            try:
                cursor = db.cursor(dictionary=True)
                cursor.execute(
                    "SELECT id, username, password, role FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
            finally:
                db.close()
        except Exception as e:
            return render_template('login.html', error=f"Database error: {str(e)}")

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials. Please try again.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/train_model', methods=['POST'])
@role_required('admin')
def train_model():
    if not os.path.exists(FACE_DATA_DIR) or not os.listdir(FACE_DATA_DIR):
        return jsonify({'status': 'error', 'message': 'No face data available to train on.'})

    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        faces = []
        ids = []

        for filename in os.listdir(FACE_DATA_DIR):
            if not filename.lower().endswith(".jpg"):
                continue

            parts = filename.replace(".jpg", "").split("_")
            if len(parts) < 3 or parts[0] != "student":
                continue

            try:
                student_id = int(parts[1])
            except ValueError:
                continue

            path = os.path.join(FACE_DATA_DIR, filename)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

            if img is None:
                continue

            faces.append(img)
            ids.append(student_id)

        if not faces:
            return jsonify({'status': 'error', 'message': 'No valid face images found for training.'})

        recognizer.train(faces, np.array(ids))
        recognizer.write(TRAINER_PATH)

        return jsonify({'status': 'success', 'message': f'Model trained on {len(faces)} face samples!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/save_face', methods=['POST'])
@role_required('admin')
def save_face():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Missing JSON data'})

        student_id = data.get('student_id')
        image_b64 = data.get('image')

        if not student_id or not image_b64:
            return jsonify({'status': 'error', 'message': 'Missing data'})

        if ',' in image_b64:
            image_b64 = image_b64.split(',')[1]

        img_data = base64.b64decode(image_b64)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            return jsonify({'status': 'error', 'message': 'Invalid image data'})

        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        os.makedirs(FACE_DATA_DIR, exist_ok=True)

        idx = len([f for f in os.listdir(FACE_DATA_DIR) if f.startswith(f"student_{student_id}_")])
        save_path = os.path.join(FACE_DATA_DIR, f"student_{student_id}_{idx}.jpg")

        cropped_face = cv2.resize(gray_img, (200, 200))
        cv2.imwrite(save_path, cropped_face)

        return jsonify({'status': 'success', 'current_count': idx + 1})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/mark_face_attendance', methods=['POST'])
@role_required('student')
def mark_face_attendance():
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'status': 'error', 'message': 'Missing image data'})

        image_b64 = data.get('image')

        if ',' in image_b64:
            image_b64 = image_b64.split(',')[1]

        img_data = base64.b64decode(image_b64)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            return jsonify({'status': 'error', 'message': 'Invalid image data'})

        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if not os.path.exists(TRAINER_PATH):
            return jsonify({'status': 'error', 'message': 'Model not trained'})

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(TRAINER_PATH)

        resized_face = cv2.resize(gray_img, (200, 200))
        label_id, confidence = recognizer.predict(resized_face)

        if label_id != session['user_id']:
            return jsonify({'status': 'error', 'message': 'Face mismatch'})

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)