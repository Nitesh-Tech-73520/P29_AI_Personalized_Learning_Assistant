import os
import sqlite3
from flask import g, current_app

SCHEMA = [
"""CREATE TABLE IF NOT EXISTS academic_details (
 student_id INTEGER PRIMARY KEY,
 college VARCHAR(200), department VARCHAR(150), branch VARCHAR(100),
 academic_year VARCHAR(20), semester VARCHAR(30), section VARCHAR(30),
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY (student_id) REFERENCES students(student_id)
)""",
"""CREATE TABLE IF NOT EXISTS students (
 student_id INTEGER PRIMARY KEY AUTO_INCREMENT,
 name VARCHAR(100) NOT NULL, email VARCHAR(150) UNIQUE NOT NULL,
 password_hash VARCHAR(255) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""",
"""CREATE TABLE IF NOT EXISTS courses (
 course_id INTEGER PRIMARY KEY AUTO_INCREMENT, course_name VARCHAR(150) NOT NULL,
 description TEXT
)""",
"""CREATE TABLE IF NOT EXISTS topics (
 topic_id INTEGER PRIMARY KEY AUTO_INCREMENT, course_id INTEGER NOT NULL,
 topic_name VARCHAR(150) NOT NULL, description TEXT,
 FOREIGN KEY (course_id) REFERENCES courses(course_id)
)""",
"""CREATE TABLE IF NOT EXISTS enrollments (
 enrollment_id INTEGER PRIMARY KEY AUTO_INCREMENT, student_id INTEGER NOT NULL,
 course_id INTEGER NOT NULL, enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(student_id, course_id),
 FOREIGN KEY (student_id) REFERENCES students(student_id),
 FOREIGN KEY (course_id) REFERENCES courses(course_id)
)""",
"""CREATE TABLE IF NOT EXISTS learning_materials (
 material_id INTEGER PRIMARY KEY AUTO_INCREMENT, topic_id INTEGER NOT NULL,
 title VARCHAR(200) NOT NULL, filename VARCHAR(255), content LONGTEXT,
 uploaded_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (topic_id) REFERENCES topics(topic_id),
 FOREIGN KEY (uploaded_by) REFERENCES students(student_id)
)""",
"""CREATE TABLE IF NOT EXISTS quiz_attempts (
 attempt_id INTEGER PRIMARY KEY AUTO_INCREMENT, student_id INTEGER NOT NULL,
 topic_id INTEGER NOT NULL, score DECIMAL(5,2) NOT NULL,
 total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0,
 attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (student_id) REFERENCES students(student_id),
 FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
)""",
"""CREATE TABLE IF NOT EXISTS recommendations (
 recommendation_id INTEGER PRIMARY KEY AUTO_INCREMENT, student_id INTEGER NOT NULL,
 topic_id INTEGER NOT NULL, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (student_id) REFERENCES students(student_id),
 FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
)"""
]

SQLITE_SCHEMA = [
"""CREATE TABLE IF NOT EXISTS academic_details (
 student_id INTEGER PRIMARY KEY, college TEXT, department TEXT, branch TEXT,
 academic_year TEXT, semester TEXT, section TEXT,
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(student_id) REFERENCES students(student_id)
)""",
"""CREATE TABLE IF NOT EXISTS students (student_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS courses (course_id INTEGER PRIMARY KEY AUTOINCREMENT, course_name TEXT NOT NULL, description TEXT)""",
"""CREATE TABLE IF NOT EXISTS topics (topic_id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, topic_name TEXT NOT NULL, description TEXT, FOREIGN KEY(course_id) REFERENCES courses(course_id))""",
"""CREATE TABLE IF NOT EXISTS enrollments (enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, course_id INTEGER NOT NULL, enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(student_id,course_id), FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(course_id) REFERENCES courses(course_id))""",
"""CREATE TABLE IF NOT EXISTS learning_materials (material_id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL, title TEXT NOT NULL, filename TEXT, content TEXT, uploaded_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(topic_id) REFERENCES topics(topic_id), FOREIGN KEY(uploaded_by) REFERENCES students(student_id))""",
"""CREATE TABLE IF NOT EXISTS quiz_attempts (attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, topic_id INTEGER NOT NULL, score REAL NOT NULL, total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(topic_id) REFERENCES topics(topic_id))""",
"""CREATE TABLE IF NOT EXISTS recommendations (recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, topic_id INTEGER NOT NULL, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(student_id) REFERENCES students(student_id), FOREIGN KEY(topic_id) REFERENCES topics(topic_id))"""
]

class DB:
    def __init__(self, conn, kind):
        self.conn, self.kind = conn, kind
    def _sql(self, sql):
        return sql.replace("%s", "?") if self.kind == "sqlite" else sql
    def execute(self, sql, params=()):
        if self.kind == "mysql":
            cur = self.conn.cursor(dictionary=True)
        else:
            cur = self.conn.cursor()
        cur.execute(self._sql(sql), params)
        return cur
    def fetchone(self, sql, params=()):
        cur = self.execute(sql, params)
        row = cur.fetchone()
        if self.kind == "sqlite" and row is not None:
            return dict(row)
        return row
    def fetchall(self, sql, params=()):
        cur = self.execute(sql, params)
        rows = cur.fetchall()
        if self.kind == "sqlite":
            return [dict(r) for r in rows]
        return rows
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()

def _connect():
    cfg = current_app.config
    if cfg["DB_TYPE"] == "sqlite":
        os.makedirs(os.path.dirname(cfg["SQLITE_PATH"]), exist_ok=True)
        conn = sqlite3.connect(cfg["SQLITE_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn, "sqlite"
    import mysql.connector
    conn = mysql.connector.connect(
        host=cfg["MYSQL_HOST"], port=cfg["MYSQL_PORT"], user=cfg["MYSQL_USER"],
        password=cfg["MYSQL_PASSWORD"], database=cfg["MYSQL_DATABASE"]
    )
    return conn, "mysql"

def get_db():
    if "db" not in g:
        conn, kind = _connect()
        g.db = DB(conn, kind)
        g.db_kind = kind
    return g.db

def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.conn.close()

def init_db():
    cfg = current_app.config
    if cfg["DB_TYPE"] == "sqlite":
        os.makedirs(os.path.dirname(cfg["SQLITE_PATH"]), exist_ok=True)
        conn = sqlite3.connect(cfg["SQLITE_PATH"])
        conn.execute("PRAGMA foreign_keys=ON")
        for statement in SQLITE_SCHEMA:
            conn.execute(statement)
        _seed(conn, "sqlite")
        conn.commit()
        conn.close()
    else:
        import mysql.connector
        conn = mysql.connector.connect(host=cfg["MYSQL_HOST"], port=cfg["MYSQL_PORT"],
            user=cfg["MYSQL_USER"], password=cfg["MYSQL_PASSWORD"], database=cfg["MYSQL_DATABASE"])
        cur = conn.cursor()
        for statement in SCHEMA:
            cur.execute(statement)
        _seed_mysql(cur)
        conn.commit()
        cur.close()
        conn.close()

def _seed(conn, kind):
    courses = [("Python Programming", "Learn Python fundamentals, functions and object-oriented programming."),
               ("Data Structures", "Understand arrays, linked lists, stacks, queues and trees."),
               ("Artificial Intelligence", "Explore AI concepts, machine learning and intelligent systems.")]
    for c in courses:
        conn.execute("INSERT OR IGNORE INTO courses(course_name,description) VALUES (?,?)", c)
    mapping = {
        "Python Programming": ["Variables and Data Types", "Loops and Conditions", "Functions", "Object-Oriented Programming"],
        "Data Structures": ["Arrays and Linked Lists", "Stacks and Queues", "Trees and Graphs"],
        "Artificial Intelligence": ["Introduction to AI", "Machine Learning Basics", "Natural Language Processing"]
    }
    for course, topics in mapping.items():
        row = conn.execute("SELECT course_id FROM courses WHERE course_name=?", (course,)).fetchone()
        for topic in topics:
            conn.execute("INSERT OR IGNORE INTO topics(course_id,topic_name) VALUES (?,?)", (row[0], topic))

def _seed_mysql(cur):
    courses = [("Python Programming", "Learn Python fundamentals, functions and object-oriented programming."),
               ("Data Structures", "Understand arrays, linked lists, stacks, queues and trees."),
               ("Artificial Intelligence", "Explore AI concepts, machine learning and intelligent systems.")]
    for c in courses:
        cur.execute("SELECT course_id FROM courses WHERE course_name=%s", (c[0],))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO courses(course_name,description) VALUES (%s,%s)", c)
    mapping = {
        "Python Programming": ["Variables and Data Types", "Loops and Conditions", "Functions", "Object-Oriented Programming"],
        "Data Structures": ["Arrays and Linked Lists", "Stacks and Queues", "Trees and Graphs"],
        "Artificial Intelligence": ["Introduction to AI", "Machine Learning Basics", "Natural Language Processing"]
    }
    for course, topics in mapping.items():
        cur.execute("SELECT course_id FROM courses WHERE course_name=%s", (course,))
        course_id = cur.fetchone()[0]
        for topic in topics:
            cur.execute("SELECT topic_id FROM topics WHERE course_id=%s AND topic_name=%s", (course_id, topic))
            if not cur.fetchone():
                cur.execute("INSERT INTO topics(course_id,topic_name) VALUES (%s,%s)", (course_id, topic))
