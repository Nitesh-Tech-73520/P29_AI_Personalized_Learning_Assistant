CREATE DATABASE IF NOT EXISTS ai_learning_assistant;
USE ai_learning_assistant;

-- The application creates/updates all required tables automatically on startup.
-- Run app.py after configuring .env.


CREATE TABLE IF NOT EXISTS academic_details (
 student_id INTEGER PRIMARY KEY,
 college VARCHAR(200), department VARCHAR(150), branch VARCHAR(100),
 academic_year VARCHAR(20), semester VARCHAR(30), section VARCHAR(30),
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (student_id) REFERENCES students(student_id)
);
