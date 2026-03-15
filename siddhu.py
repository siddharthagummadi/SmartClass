from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import random
import string
import time
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Enable CORS for cross-origin requests (if needed)
CORS(app)

# MySQL Database Connection
db = mysql.connector.connect(
    host='localhost',
    user='root',
    password='12345',
    database='smartclass'
)
cursor = db.cursor()

# Home Route (Redirects to Login)
@app.route('/')
def home():
    return redirect(url_for('login'))

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT id, username, role FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[2]

            if user[2] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user[2] == 'student':
                return redirect(url_for('student_dashboard'))
            else:
                return render_template('login.html', error="Invalid role assigned. Contact admin.")
        else:
            return render_template('login.html', error="Invalid credentials. Please try again.")

    return render_template('login.html')

# Teacher Dashboard Route
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'user_id' in session and session['role'] == 'teacher':
        teacher_name = session['username']
        return render_template('teacher_dashboard.html', teacher_name=teacher_name)
    return redirect(url_for('login'))

# Student Dashboard Route
@app.route('/student_dashboard')
def student_dashboard():
    if 'user_id' in session and session['role'] == 'student':
        return render_template('student_dashboard.html')
    return redirect(url_for('login'))

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Generate Unique QR Code (Updated every 10-15 seconds)
@app.route('/generate_qr')
def generate_qr():
    if 'user_id' in session and session['role'] == 'teacher':
        qr_length = 10
        qr_expiry_seconds = 15

        unique_code = ''.join(random.choices(string.ascii_letters + string.digits, k=qr_length))  
        timestamp = int(time.time())

        try:
            cursor.execute("""
                REPLACE INTO qr_codes (teacher_id, qr_value, generated_at)
                VALUES (%s, %s, %s)
            """, (session['user_id'], unique_code, timestamp))
            db.commit()

            print(f"✅ [{time.strftime('%H:%M:%S')}] QR Code Generated: {unique_code}")

            return jsonify({
                'qr_code': unique_code,
                'expires_in': qr_expiry_seconds
            })
        except Exception as e:
            print(f"❌ [{time.strftime('%H:%M:%S')}] QR Generation Error: {str(e)}")
            return jsonify({'error': 'QR generation failed due to server error'}), 500

    return jsonify({'error': 'Unauthorized access'}), 403

# Validate Scanned QR Code
@app.route('/validate_qr', methods=['POST'])
def validate_qr():
    if 'user_id' in session and session['role'] == 'student':
        scanned_code = request.json.get('qr_code')
        current_time = int(time.time())

        try:
            cursor.execute("""
                SELECT teacher_id FROM qr_codes 
                WHERE qr_value = %s AND generated_at >= %s
            """, (scanned_code, current_time - 15))
            result = cursor.fetchone()

            if result:
                print(f"✅ [{time.strftime('%H:%M:%S')}] QR Code Validated for Student ID: {session['user_id']}")
                return jsonify({'status': 'valid'})
            else:
                print(f"❌ [{time.strftime('%H:%M:%S')}] Invalid/Expired QR Scanned: {scanned_code}")
                return jsonify({'status': 'invalid'})
        except Exception as e:
            print(f"❌ [{time.strftime('%H:%M:%S')}] QR Validation Error: {str(e)}")
            return jsonify({'error': 'Validation error'}), 500

    return jsonify({'error': 'Unauthorized access'}), 403

# Route to fetch students and display them on the manual attendance page
@app.route('/mark_manual_attendance', methods=['GET', 'POST'])
def mark_manual_attendance():
    if 'user_id' in session and session['role'] == 'teacher':  # Check if the user is logged in and is a teacher
        if request.method == 'POST':
            attendance_data = request.json.get('attendance')  # Expecting JSON data from frontend

            try:
                # Mark attendance for each student
                for entry in attendance_data:
                    student_id = entry['student_id']
                    is_present = entry['present']
                    
                    # Insert attendance data into the database
                    cursor.execute("""INSERT INTO attendance (student_id, teacher_id, is_present, date) 
                                    VALUES (%s, %s, %s, NOW())""", (student_id, session['user_id'], is_present))
                    db.commit()

                return jsonify({'status': 'Attendance marked successfully'})
            except Exception as e:
                print(f"❌ Error marking attendance: {str(e)}")
                return jsonify({'error': f'Error marking attendance: {str(e)}'}), 500

        # If GET request, render manual attendance form
        cursor.execute("SELECT student_id, name, roll_no FROM students")  # Get all students from the database
        students = cursor.fetchall()

        return render_template('mark_manual_attendance.html', students=students)  # Pass students data to HTML page

    return redirect(url_for('login'))  # If the user is not logged in, redirect to the login page


# Run the App
if __name__ == '__main__':
    app.run(debug=True, port=5001)
