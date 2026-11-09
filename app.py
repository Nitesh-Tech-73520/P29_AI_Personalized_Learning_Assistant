import os
import re
import random
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config
from database import init_db, get_db, close_db
from learning_engine import answer_question, build_quiz, recommend_topics
from document_utils import extract_text
from ednet.loader import dataset_stats, learner_summary

app = Flask(__name__)
app.config.from_object(Config)
app.teardown_appcontext(close_db)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("student_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.before_request
def ensure_database():
    # Database creation is handled by init_db() at startup.
    pass

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email and a password of at least 8 characters.", "danger")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO students (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password))
            )
            db.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as exc:
            db.rollback()
            print("Registration error:", exc)
            flash("That email may already be registered. Please try another.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        student = db.fetchone("SELECT * FROM students WHERE email = %s", (email,))
        if student and check_password_hash(student["password_hash"], password):
            session.clear()
            session["student_id"] = student["student_id"]
            session["student_name"] = student["name"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    sid = session["student_id"]
    stats = {
        "courses": db.fetchone("SELECT COUNT(*) AS n FROM enrollments WHERE student_id=%s", (sid,))["n"],
        "quizzes": db.fetchone("SELECT COUNT(*) AS n FROM quiz_attempts WHERE student_id=%s", (sid,))["n"],
        "average": db.fetchone("SELECT AVG(score) AS n FROM quiz_attempts WHERE student_id=%s", (sid,))["n"] or 0,
    }
    recommendations = recommend_topics(db, sid)
    recent = db.fetchall(
        """SELECT qa.score, qa.attempted_at, t.topic_name, c.course_name
           FROM quiz_attempts qa JOIN topics t ON qa.topic_id=t.topic_id
           JOIN courses c ON t.course_id=c.course_id
           WHERE qa.student_id=%s ORDER BY qa.attempted_at DESC LIMIT 5""", (sid,)
    )
    return render_template("dashboard.html", stats=stats, recommendations=recommendations, recent=recent)


@app.route("/academic", methods=["GET", "POST"])
@login_required
def academic():
    db = get_db()
    student_id = session["student_id"]
    academic = db.fetchone(
        "SELECT * FROM academic_details WHERE student_id=%s", (student_id,)
    )

    if request.method == "POST":
        fields = {
            "college": request.form.get("college", "").strip(),
            "department": request.form.get("department", "").strip(),
            "branch": request.form.get("branch", "").strip(),
            "academic_year": request.form.get("academic_year", "").strip(),
            "semester": request.form.get("semester", "").strip(),
            "section": request.form.get("section", "").strip(),
        }
        limits = {"college": 200, "department": 150, "branch": 100,
                  "academic_year": 20, "semester": 30, "section": 30}
        if any(len(value) > limits[key] for key, value in fields.items()):
            flash("One or more academic fields are too long.", "danger")
            return redirect(url_for("academic"))

        values = tuple(fields[key] for key in (
            "college", "department", "branch", "academic_year", "semester", "section"
        ))
        try:
            if academic:
                db.execute(
                    """UPDATE academic_details SET college=%s, department=%s, branch=%s,
                       academic_year=%s, semester=%s, section=%s WHERE student_id=%s""",
                    values + (student_id,)
                )
            else:
                db.execute(
                    """INSERT INTO academic_details
                       (student_id, college, department, branch, academic_year, semester, section)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (student_id,) + values
                )
            db.commit()
            flash("Academic information saved successfully.", "success")
        except Exception as exc:
            db.rollback()
            app.logger.exception("Could not save academic details: %s", exc)
            flash("Could not save academic information. Check the application terminal.", "danger")
        return redirect(url_for("academic"))

    return render_template("academic.html", academic=academic)

@app.route("/profile")
@login_required
def profile():
    db = get_db()
    student = db.fetchone(
        "SELECT student_id, name, email, created_at FROM students WHERE student_id=%s",
        (session["student_id"],)
    )
    if not student:
        flash("Student profile could not be found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("profile.html", student=student)


@app.route("/courses")
@login_required
def courses():
    db = get_db()
    rows = db.fetchall(
        """SELECT c.*, (SELECT COUNT(*) FROM topics t WHERE t.course_id=c.course_id) AS topic_count,
           (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.course_id AND e.student_id=%s) AS enrolled
           FROM courses c ORDER BY c.course_name""", (session["student_id"],)
    )
    return render_template("courses.html", courses=rows)

@app.route("/courses/<int:course_id>")
@login_required
def course_detail(course_id):
    db = get_db()
    course = db.fetchone("SELECT * FROM courses WHERE course_id=%s", (course_id,))
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))
    topics = db.fetchall(
        """SELECT t.*, (SELECT COUNT(*) FROM learning_materials m WHERE m.topic_id=t.topic_id) AS material_count
           FROM topics t WHERE t.course_id=%s ORDER BY t.topic_name""", (course_id,)
    )
    return render_template("course_detail.html", course=course, topics=topics)

@app.route("/courses/<int:course_id>/enroll", methods=["POST"])
@login_required
def enroll(course_id):
    db = get_db()
    try:
        db.execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)",
                   (session["student_id"], course_id))
        db.commit()
        flash("You are enrolled in this course.", "success")
    except Exception:
        db.rollback()
        flash("You are already enrolled or the course is unavailable.", "info")
    return redirect(url_for("course_detail", course_id=course_id))

@app.route("/materials")
@login_required
def materials():
    db = get_db()
    rows = db.fetchall(
        """SELECT m.*, t.topic_name, c.course_name FROM learning_materials m
           JOIN topics t ON m.topic_id=t.topic_id JOIN courses c ON t.course_id=c.course_id
           ORDER BY m.created_at DESC"""
    )
    topics = db.fetchall("SELECT t.topic_id, t.topic_name, c.course_name FROM topics t JOIN courses c ON t.course_id=c.course_id ORDER BY c.course_name, t.topic_name")
    return render_template("materials.html", materials=rows, topics=topics)

@app.route("/materials/upload", methods=["POST"])
@login_required
def upload_material():
    topic_id = request.form.get("topic_id", type=int)
    title = request.form.get("title", "").strip()
    file = request.files.get("file")
    if not topic_id or not title or not file or not file.filename:
        flash("Choose a topic, title and file.", "danger")
        return redirect(url_for("materials"))
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".pdf", ".txt"}:
        flash("Only PDF and TXT files are supported.", "danger")
        return redirect(url_for("materials"))
    stored = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], stored)
    file.save(path)
    try:
        content = extract_text(path, ext)
        if not content.strip():
            raise ValueError("No readable text found. Scanned PDFs need OCR, which is not included.")
        db = get_db()
        db.execute(
            "INSERT INTO learning_materials (topic_id, title, filename, content, uploaded_by) VALUES (%s, %s, %s, %s, %s)",
            (topic_id, title, stored, content, session["student_id"])
        )
        db.commit()
        flash("Material uploaded and indexed for the AI tutor.", "success")
    except Exception as exc:
        if os.path.exists(path):
            os.remove(path)
        flash(f"Could not process file: {exc}", "danger")
    return redirect(url_for("materials"))

@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html")

@app.route("/api/chat", methods=["POST"])
@login_required
def chat_api():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()
    if not question:
        return jsonify({"answer": "Please type a question first.", "sources": []}), 400
    db = get_db()
    answer, sources = answer_question(db, session["student_id"], question)
    return jsonify({"answer": answer, "sources": sources})

@app.route("/quiz")
@login_required
def quiz():
    db = get_db()
    topics = db.fetchall("SELECT t.topic_id, t.topic_name, c.course_name FROM topics t JOIN courses c ON t.course_id=c.course_id ORDER BY c.course_name, t.topic_name")
    return render_template("quiz.html", topics=topics)

@app.route("/quiz/<int:topic_id>", methods=["GET", "POST"])
@login_required
def take_quiz(topic_id):
    db = get_db()
    topic = db.fetchone("SELECT t.*, c.course_name FROM topics t JOIN courses c ON t.course_id=c.course_id WHERE t.topic_id=%s", (topic_id,))
    if not topic:
        flash("Topic not found.", "danger")
        return redirect(url_for("quiz"))
    if request.method == "POST":
        questions = build_quiz(db, topic_id, 5)
        if not questions:
            flash("Upload learning material for this topic before generating a quiz.", "warning")
            return redirect(url_for("quiz"))
        submitted = request.form
        correct = sum(1 for i, q in enumerate(questions) if submitted.get(f"q{i}") == str(q["answer"]))
        score = round(correct / len(questions) * 100, 2)
        db.execute("INSERT INTO quiz_attempts (student_id, topic_id, score, total_questions, correct_answers) VALUES (%s, %s, %s, %s, %s)",
                   (session["student_id"], topic_id, score, len(questions), correct))
        db.commit()
        return render_template("quiz_result.html", score=score, correct=correct, total=len(questions), topic=topic)
    questions = build_quiz(db, topic_id, 5)
    if not questions:
        flash("No quiz material is available yet. Upload a PDF or TXT file first.", "warning")
        return redirect(url_for("quiz"))
    return render_template("take_quiz.html", topic=topic, questions=questions)

@app.route("/progress")
@login_required
def progress():
    db = get_db()
    rows = db.fetchall(
        """SELECT qa.score, qa.attempted_at, qa.total_questions, qa.correct_answers,
           t.topic_name, c.course_name FROM quiz_attempts qa
           JOIN topics t ON qa.topic_id=t.topic_id JOIN courses c ON t.course_id=c.course_id
           WHERE qa.student_id=%s ORDER BY qa.attempted_at DESC""", (session["student_id"],)
    )
    return render_template("progress.html", attempts=rows)


@app.route("/ednet")
@login_required
def ednet_dashboard():
    dataset_dir = os.path.join(os.path.dirname(__file__), "data", "EdNet", "KT1")
    if not os.path.isdir(dataset_dir):
        return render_template("ednet.html", available=False, stats=None, learner=None)
    stats = dataset_stats(dataset_dir, sample_limit=50000)
    # User ID in the app is not an EdNet learner ID; show dataset-level metrics.
    return render_template("ednet.html", available=True, stats=stats, learner=None)

@app.route("/health")
def health():
    try:
        db = get_db()
        db.fetchone("SELECT 1 AS ok")
        return jsonify({"status": "ok", "database": "connected"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

if __name__ == "__main__":
 with app.app_context():
    init_db()
    app.run(debug=True)
