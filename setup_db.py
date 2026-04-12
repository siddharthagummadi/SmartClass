import os
import mysql.connector
from werkzeug.security import generate_password_hash


def get_db_connection_without_db():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST') or os.getenv('MYSQLHOST') or 'localhost',
        user=os.getenv('MYSQL_USER') or os.getenv('MYSQLUSER') or 'root',
        password=os.getenv('MYSQL_PASSWORD') or os.getenv('MYSQLPASSWORD') or '1605',
        port=int(os.getenv('MYSQL_PORT') or os.getenv('MYSQLPORT') or 3306)
    )


def get_db():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST') or os.getenv('MYSQLHOST') or 'localhost',
        user=os.getenv('MYSQL_USER') or os.getenv('MYSQLUSER') or 'root',
        password=os.getenv('MYSQL_PASSWORD') or os.getenv('MYSQLPASSWORD') or '1605',
        database=os.getenv('MYSQL_DATABASE') or os.getenv('MYSQLDATABASE') or 'smartclass',
        port=int(os.getenv('MYSQL_PORT') or os.getenv('MYSQLPORT') or 3306)
    )


def create_database():
    db_name = os.getenv('MYSQL_DATABASE') or os.getenv('MYSQLDATABASE') or 'smartclass'

    # ✅ Step 1: Ensure database exists if possible
    try:
        db = get_db_connection_without_db()
        cursor = db.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"[SUCCESS] Database '{db_name}' ensured.")
        db.close()
    except Exception as e:
        print(f"[INFO] Skipping DB creation (might already exist or restricted permissions): {e}")

    # ✅ Step 2: Connect to DB and create tables
    try:
        db = get_db()
        cursor = db.cursor()

        # --- TABLES ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('admin', 'teacher', 'student') NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                teacher_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                roll_no VARCHAR(50) UNIQUE NOT NULL,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qr_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                teacher_id INT,
                qr_value VARCHAR(255) UNIQUE NOT NULL,
                generated_at BIGINT NOT NULL,
                FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

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

        print("[SUCCESS] Tables created successfully!")

        # --- DEFAULT DATA ---
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            print("[INFO] Inserting default users...")

            admin_pwd = generate_password_hash("admin")
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, 'admin')",
                ("admin", admin_pwd)
            )

            db.commit()
            print("[SUCCESS] Default admin inserted!")

    except mysql.connector.Error as err:
        print(f"[ERROR] MySQL Error: {err}")
    finally:
        if 'db' in locals() and db.is_connected():
            db.close()
            print("[INFO] Database connection closed.")


if __name__ == "__main__":
    create_database()