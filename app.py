from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
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

# Initialize connection pool
db_config = {
    "host": os.getenv('MYSQL_HOST') or os.getenv('MYSQLHOST') or 'localhost',
    "user": os.getenv('MYSQL_USER') or os.getenv('MYSQLUSER') or 'root',
    "password": os.getenv('MYSQL_PASSWORD') or os.getenv('MYSQLPASSWORD') or '1605',
    "database": os.getenv('MYSQL_DATABASE') or os.getenv('MYSQLDATABASE') or 'smartclass',
    "port": int(os.getenv('MYSQL_PORT') or os.getenv('MYSQLPORT') or 3306)
}

try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="smartclass_pool",
        pool_size=5,
        **db_config
    )
except Exception as e:
    print(f"Error creating connection pool: {e}")
    db_pool = None

def get_db():
    if db_pool:
        return db_pool.get_connection()
    return mysql.connector.connect(**db_config)

@contextmanager
def db_session(dictionary=True):
    conn = get_db()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

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
            with db_session(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT id, username, password, role FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
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

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    try:
        with db_session(dictionary=False) as cursor:
            # Get counts for the dashboard
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
            total_students = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher'")
            total_teachers = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM attendance")
            total_attendance = cursor.fetchone()[0]
            
        return render_template('admin_dashboard.html', 
                               total_students=total_students, 
                               total_teachers=total_teachers, 
                               total_attendance=total_attendance)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}")
        return redirect(url_for('login'))

@app.route('/teacher/dashboard')
@role_required('teacher')
def teacher_dashboard():
    try:
        with db_session(dictionary=True) as cursor:
            cursor.execute("SELECT name FROM teachers WHERE user_id = %s", (session['user_id'],))
            teacher = cursor.fetchone()
        
        teacher_name = teacher['name'] if teacher else session.get('username', 'Teacher')
        return render_template('teacher_dashboard.html', teacher_name=teacher_name)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}")
        return redirect(url_for('login'))

@app.route('/student/dashboard')
@role_required('student')
def student_dashboard():
    return render_template('student_dashboard.html')

@app.route('/admin/manage_students', methods=['GET', 'POST'])
@role_required('admin')
def manage_students():
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            with db_session(dictionary=True) as cursor:
                if action == 'add':
                    name = request.form.get('name')
                    roll_no = request.form.get('roll_no')
                    username = request.form.get('username')
                    password = generate_password_hash(request.form.get('password'))
                    
                    # Insert into users table
                    cursor.execute(
                        "INSERT INTO users (username, password, role) VALUES (%s, %s, 'student')",
                        (username, password)
                    )
                    user_id = cursor.lastrowid
                    
                    # Insert into students table
                    cursor.execute(
                        "INSERT INTO students (student_id, name, roll_no, user_id) VALUES (%s, %s, %s, %s)",
                        (user_id, name, roll_no, user_id)
                    )
                    flash("Student added successfully!")
                
                elif action == 'delete':
                    user_id = request.form.get('user_id')
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    flash("Student deleted successfully!")
        except Exception as e:
            flash(f"Error: {str(e)}")
    
    # GET request or after POST
    try:
        with db_session(dictionary=True) as cursor:
            cursor.execute("""
                SELECT s.name, s.roll_no, u.username, u.id as user_id 
                FROM students s 
                JOIN users u ON s.user_id = u.id
            """)
            students = cursor.fetchall()
            
            # Calculate sample counts for each student
            for student in students:
                student['sample_count'] = len([
                    f for f in os.listdir(FACE_DATA_DIR) 
                    if f.startswith(f"student_{student['user_id']}_")
                ]) if os.path.exists(FACE_DATA_DIR) else 0

            return render_template('manage_students.html', students=students)
    except Exception as e:
        flash(f"Error loading students: {str(e)}")
        return redirect(url_for('admin_dashboard'))

# Consolidate redundant routes
@app.route('/admin_dashboard')
@app.route('/manage_students')
@app.route('/manage_teachers')
@role_required('admin')
def admin_shortcuts():
    # Redirect to canonical versions
    if request.path == '/admin_dashboard': return redirect(url_for('admin_dashboard'))
    if request.path == '/manage_students': return redirect(url_for('manage_students'))
    if request.path == '/manage_teachers': return redirect(url_for('manage_teachers'))
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/manage_teachers', methods=['GET', 'POST'])
@role_required('admin')
def manage_teachers():
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            with db_session(dictionary=True) as cursor:
                if action == 'add':
                    name = request.form.get('name')
                    username = request.form.get('username')
                    password = generate_password_hash(request.form.get('password'))
                    
                    cursor.execute(
                        "INSERT INTO users (username, password, role) VALUES (%s, %s, 'teacher')",
                        (username, password)
                    )
                    user_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO teachers (teacher_id, name, user_id) VALUES (%s, %s, %s)",
                        (user_id, name, user_id)
                    )
                    flash("Teacher added successfully!")
                
                elif action == 'delete':
                    user_id = request.form.get('user_id')
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    flash("Teacher deleted successfully!")
        except Exception as e:
            flash(f"Error: {str(e)}")
    
    try:
        with db_session(dictionary=True) as cursor:
            cursor.execute("""
                SELECT t.name, u.username, u.id as user_id 
                FROM teachers t 
                JOIN users u ON t.user_id = u.id
            """)
            teachers = cursor.fetchall()
            return render_template('manage_teachers.html', teachers=teachers)
    except Exception as e:
        flash(f"Error loading teachers: {str(e)}")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/capture_face/<int:user_id>')
@role_required('admin')
def admin_capture_face(user_id):
    try:
        with db_session(dictionary=True) as cursor:
            cursor.execute("SELECT name FROM students WHERE user_id = %s", (user_id,))
            student = cursor.fetchone()
        
        student_name = student['name'] if student else "Unknown"
        return render_template('capture_face.html', student_id=user_id, student_name=student_name)
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('manage_students'))

@app.route('/admin/clear_face_data/<int:user_id>', methods=['POST'])
@role_required('admin')
def clear_face_data(user_id):
    try:
        if os.path.exists(FACE_DATA_DIR):
            files = [f for f in os.listdir(FACE_DATA_DIR) if f.startswith(f"student_{user_id}_")]
            for f in files:
                os.remove(os.path.join(FACE_DATA_DIR, f))
            return jsonify({'status': 'success', 'message': f'Cleared {len(files)} image(s).'})
        return jsonify({'status': 'error', 'message': 'Data directory not found.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/train_model', methods=['POST'])
@role_required('admin')
def train_model():
    if not os.path.exists(FACE_DATA_DIR) or not os.listdir(FACE_DATA_DIR):
        return jsonify({'status': 'error', 'message': 'No face data available to train on.'})

    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        faces = []
        ids = []
        unique_students = set()

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
            unique_students.add(student_id)

        if not faces:
            return jsonify({'status': 'error', 'message': 'No valid face images found for training.'})

        recognizer.train(faces, np.array(ids))
        recognizer.write(TRAINER_PATH)

        return jsonify({
            'status': 'success', 
            'message': f'Model trained successfully!',
            'details': f'Trained on {len(faces)} samples across {len(unique_students)} students.'
        })
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

@app.route('/generate_qr')
@role_required('teacher')
def generate_qr():
    try:
        qr_value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))
        generated_at = int(time.time())
        
        with db_session(dictionary=False) as cursor:
            cursor.execute(
                "INSERT INTO qr_codes (teacher_id, qr_value, generated_at) VALUES (%s, %s, %s)",
                (session['user_id'], qr_value, generated_at)
            )
        
        return jsonify({
            'qr_code': qr_value,
            'expires_in': 15  # seconds
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/validate_qr', methods=['POST'])
@role_required('student')
def validate_qr():
    try:
        data = request.get_json()
        qr_value = data.get('qr_code')
        
        with db_session(dictionary=True) as cursor:
            # Find QR code and ensure it's not older than 20 seconds (allowing some latency)
            cursor.execute(
                "SELECT teacher_id, generated_at FROM qr_codes WHERE qr_value = %s",
                (qr_value,)
            )
            qr_record = cursor.fetchone()
        
        if qr_record:
            current_time = int(time.time())
            if current_time - qr_record['generated_at'] <= 20:
                # Store teacher_id in session to use for marking attendance later
                session['pending_teacher_id'] = qr_record['teacher_id']
                return jsonify({'status': 'valid'})
        
        return jsonify({'status': 'invalid'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/face_recognition')
@role_required('student')
def face_recognition():
    if 'pending_teacher_id' not in session:
        return redirect(url_for('student_dashboard'))
    return render_template('face_recognition.html')

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

        # confidence is distance, lower is better. 0-100 threshold is typical
        if label_id == session['user_id'] and confidence < 70:
            # Mark attendance in DB
            teacher_id = session.get('pending_teacher_id')
            if not teacher_id:
                return jsonify({'status': 'error', 'message': 'No pending session found'})
            
            with db_session(dictionary=False) as cursor:
                cursor.execute(
                    "INSERT INTO attendance (student_id, teacher_id, is_present) VALUES (%s, %s, 1)",
                    (session['user_id'], teacher_id)
                )
            
            # Clear pending session
            session.pop('pending_teacher_id', None)
            
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Face mismatch or low confidence'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/mark_manual_attendance', methods=['GET', 'POST'])
@role_required('teacher')
def mark_manual_attendance():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            attendance_list = data.get('attendance', [])
            
            for item in attendance_list:
                if item.get('present'):
                    cursor.execute(
                        "INSERT INTO attendance (student_id, teacher_id, is_present) VALUES (%s, %s, 1)",
                        (item['student_id'], session['user_id'])
                    )
            db.commit()
            return jsonify({'status': True})
        except Exception as e:
            db.rollback()
            return jsonify({'status': False, 'error': str(e)})
        finally:
            db.close()
    
    try:
        with db_session(dictionary=True) as cursor:
            # GET request: fetch all students
            cursor.execute("SELECT user_id, name, roll_no FROM students")
            students_data = cursor.fetchall()
        
        # Convert to list of tuples for the template
        students = [(s['user_id'], s['name'], s['roll_no']) for s in students_data]
        return render_template('mark_manual_attendance.html', students=students)
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('teacher_dashboard'))

@app.route('/api/attendance_report')
@role_required('teacher')
def api_attendance_report():
    try:
        with db_session(dictionary=True) as cursor:
            cursor.execute("""
                SELECT s.name, s.roll_no as rollNumber, 
                       IF(a.is_present=1, 'Present', 'Absent') as attendance,
                       a.date as time
                FROM students s
                LEFT JOIN attendance a ON s.user_id = a.student_id AND a.teacher_id = %s
                ORDER BY a.date DESC
            """, (session['user_id'],))
            records = cursor.fetchall()
        
        # Format dates for JSON
        for r in records:
            if r['time']:
                r['time'] = r['time'].strftime('%Y-%m-%d %H:%M:%S')
            else:
                r['time'] = 'N/A'
                r['attendance'] = 'Absent'

        return jsonify({'status': 'success', 'data': records})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/api/student_attendance')
@role_required('student')
def api_student_attendance():
    try:
        with db_session(dictionary=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = %s", (session['user_id'],))
            present_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT DATE(date)) FROM attendance")
            total_days = cursor.fetchone()[0] or 1
        
        percentage = round((present_count / total_days) * 100) if total_days > 0 else 0
        
        return jsonify({'status': 'success', 'percentage': min(percentage, 100)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/export/excel')
@role_required('teacher')
def export_excel():
    try:
        conn = get_db()
        try:
            df = pd.read_sql("""
                SELECT s.name, s.roll_no, IF(a.is_present=1, 'Present', 'Absent') as attendance, a.date
                FROM students s
                LEFT JOIN attendance a ON s.user_id = a.student_id AND a.teacher_id = %s
            """, conn, params=(session['user_id'],))
        finally:
            conn.close()
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance')
        output.seek(0)
        
        return send_file(output, download_name="attendance_report.xlsx", as_attachment=True)
    except Exception as e:
        return str(e), 500

@app.route('/api/export/pdf')
@role_required('teacher')
def export_pdf():
    try:
        with db_session(dictionary=True) as cursor:
            cursor.execute("""
                SELECT s.name, s.roll_no, IF(a.is_present=1, 'Present', 'Absent') as attendance, a.date
                FROM students s
                LEFT JOIN attendance a ON s.user_id = a.student_id AND a.teacher_id = %s
            """, (session['user_id'],))
            records = cursor.fetchall()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        data = [['Name', 'Roll No', 'Attendance', 'Date']]
        for r in records:
            data.append([r['name'], r['roll_no'], r['attendance'], str(r['date'])])
            
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        doc.build([table])
        buffer.seek(0)
        return send_file(buffer, download_name="attendance_report.pdf", as_attachment=True)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)