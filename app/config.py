import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'pass-it-on-campus-secure-key-98234-change-in-prod')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'campus.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    
    # Session & Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
