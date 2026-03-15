import os
import mysql.connector
from werkzeug.security import generate_password_hash


def get_db():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST') or os.getenv('MYSQLHOST') or 'localhost',
        user=os.getenv('MYSQL_USER') or os.getenv('MYSQLUSER') or 'root',
        password=os.getenv('MYSQL_PASSWORD') or os.getenv('MYSQLPASSWORD') or '1605',
        database=os.getenv('MYSQL_DATABASE') or os.getenv('MYSQLDATABASE') or 'smartclass',
        port=int(os.getenv('MYSQL_PORT') or os.getenv('MYSQLPORT') or 3306)
    )


def create_database():
    try:
        db = get_db()
        cursor = db.cursor()

        # 1. Create Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('admin', 'teacher', 'student') NOT NULL
            )
        """)

        # 2. Create Admins Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 3. Create Teachers Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                teacher_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 4. Create Students Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                roll_no VARCHAR(50) UNIQUE NOT NULL,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 5. Create Face Encodings Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_encodings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT UNIQUE,
                encoding LONGTEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 6. Create QR Codes Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qr_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                teacher_id INT,
                qr_value VARCHAR(255) UNIQUE NOT NULL,
                generated_at BIGINT NOT NULL,
                FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 7. Create Attendance Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT,
                teacher_id INT,
                is_present TINYINT(1) NOT NULL DEFAULT 0,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 8. Create Face Data Images Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_data_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT,
                image_blob LONGBLOB NOT NULL,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 9. Create Face Model Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_model (
                id INT AUTO_INCREMENT PRIMARY KEY,
                model_blob LONGBLOB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        print("[SUCCESS] All MySQL tables created successfully!")

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            print("[INFO] Inserting default users...")

            # Admins
            admins_data = [
                ('admin', 'admin', 'System Admin'),
                ('admin2', 'admin2', 'Academic Admin'),
                ('superadmin', 'superadmin', 'Super Admin')
            ]
            for a_user, a_pass, a_name in admins_data:
                admin_pwd = generate_password_hash(a_pass)
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, 'admin')",
                    (a_user, admin_pwd)
                )
                admin_user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO admins (admin_id, name, user_id) VALUES (%s, %s, %s)",
                    (admin_user_id, a_name, admin_user_id)
                )

            # Teachers
            teachers_data = [
                ('Dr. Rajesh Kumar', 'rajesh', 'rajesh123'),
                ('Prof. Anita Sharma', 'anita', 'anita123'),
                ('Dr. Vikram Singh', 'vikram', 'vikram123'),
                ('Prof. Meena Iyer', 'meena', 'meena123'),
                ('Dr. Arjun Reddy', 'arjun', 'arjun123'),
                ('Prof. Kavita Rao', 'kavita', 'kavita123'),
                ('Dr. Suresh Patel', 'suresh', 'suresh123'),
                ('Prof. Neha Verma', 'neha', 'neha123'),
                ('Dr. Rakesh Gupta', 'rakesh', 'rakesh123'),
                ('Prof. Lakshmi Narayan', 'lakshmi', 'lakshmi123'),
                ('Dr. Deepak Mishra', 'deepak', 'deepak123'),
                ('Prof. Sunita Kapoor', 'sunita', 'sunita123'),
                ('Dr. Mohan Das', 'mohan', 'mohan123')
            ]
            for t_name, t_user, t_pass in teachers_data:
                hashed_pwd = generate_password_hash(t_pass)
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, 'teacher')",
                    (t_user, hashed_pwd)
                )
                user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO teachers (teacher_id, name, user_id) VALUES (%s, %s, %s)",
                    (user_id, t_name, user_id)
                )

            # Students
            students_data = [
                ('siddhu', 'siddhu', 'R001', 'Siddhartha Gummadi'),
                ('ravi', 'ravi', 'R002', 'Ravi Kumar'),
                ('sita', 'sita', 'R003', 'Sita Rani'),
                ('vijay', 'vijay', 'R004', 'Vijay Kumar'),
                ('rahul', 'rahul', 'R005', 'Rahul Sharma'),
                ('priya', 'priya', 'R006', 'Priya Nair'),
                ('karthik', 'karthik', 'R007', 'Karthik Reddy'),
                ('anjali', 'anjali', 'R008', 'Anjali Singh'),
                ('rohit', 'rohit', 'R009', 'Rohit Verma'),
                ('sneha', 'sneha', 'R010', 'Sneha Patel'),
                ('aman', 'aman', 'R011', 'Aman Gupta'),
                ('kavya', 'kavya', 'R012', 'Kavya Iyer'),
                ('arjun_s', 'arjun', 'R013', 'Arjun Singh'),
                ('pooja', 'pooja', 'R014', 'Pooja Sharma'),
                ('nikhil', 'nikhil', 'R015', 'Nikhil Reddy'),
                ('swathi', 'swathi', 'R016', 'Swathi Rao'),
                ('harish', 'harish', 'R017', 'Harish Kumar'),
                ('keerthi', 'keerthi', 'R018', 'Keerthi Nair'),
                ('aditya', 'aditya', 'R019', 'Aditya Verma'),
                ('divya', 'divya', 'R020', 'Divya Patel'),
                ('varun', 'varun', 'R021', 'Varun Gupta'),
                ('neha_s', 'neha', 'R022', 'Neha Sharma'),
                ('manish', 'manish', 'R023', 'Manish Singh'),
                ('ritu', 'ritu', 'R024', 'Ritu Kapoor'),
                ('abhi', 'abhi', 'R025', 'Abhishek Kumar'),
                ('tanvi', 'tanvi', 'R026', 'Tanvi Nair'),
                ('suraj', 'suraj', 'R027', 'Suraj Reddy'),
                ('pavan', 'pavan', 'R028', 'Pavan Kumar'),
                ('bhavana', 'bhavana', 'R029', 'Bhavana Iyer'),
                ('ashwin', 'ashwin', 'R030', 'Ashwin Patel'),
                ('gopal', 'gopal', 'R031', 'Gopal Krishna'),
                ('harika', 'harika', 'R032', 'Harika Reddy'),
                ('naveen', 'naveen', 'R033', 'Naveen Kumar'),
                ('pranav', 'pranav', 'R034', 'Pranav Sharma'),
                ('saiteja', 'saiteja', 'R035', 'Sai Teja'),
                ('lakshmi_p', 'lakshmi', 'R036', 'Lakshmi Priya'),
                ('deepika', 'deepika', 'R037', 'Deepika Singh'),
                ('akash', 'akash', 'R038', 'Akash Verma'),
                ('shreya', 'shreya', 'R039', 'Shreya Kapoor'),
                ('yash', 'yash', 'R040', 'Yash Patel')
            ]
            for username, password, roll_no, name in students_data:
                hashed_pwd = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, 'student')",
                    (username, hashed_pwd)
                )
                user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO students (student_id, name, roll_no, user_id) VALUES (%s, %s, %s, %s)",
                    (user_id, name, roll_no, user_id)
                )

            db.commit()
            print("[SUCCESS] Default MySQL records inserted!")

    except mysql.connector.Error as err:
        print(f"[ERROR] MySQL Error: {err}")
    finally:
        if 'db' in locals() and db.is_connected():
            db.close()
            print("[INFO] Database connection closed.")


if __name__ == "__main__":
    create_database()