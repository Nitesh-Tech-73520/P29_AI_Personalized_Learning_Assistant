import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-development-secret-before-deployment")
    DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ai_learning_assistant")
    SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "instance" / "ai_learning_assistant.db"))
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "txt"}
