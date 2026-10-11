"""
NativeFrames — Application Configuration
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _db_uri():
    """Build MySQL URI from DATABASE_URL env var or individual fields with seamless local fallback."""
    if os.environ.get('USE_SQLITE', '').lower() in ('1', 'true'):
        return 'sqlite:///nativeframes.db'

    url = os.environ.get('DATABASE_URL', '')
    if url:
        if url.startswith('sqlite:'):
            return url
        # Ensure we use the pymysql driver
        if url.startswith('mysql://'):
            url = url.replace('mysql://', 'mysql+pymysql://', 1)

        # If pointing to internal Railway domain from a local machine outside Railway
        if 'railway.internal' in url:
            import socket
            try:
                socket.gethostbyname('mysql.railway.internal')
            except (socket.gaierror, OSError):
                return 'sqlite:///nativeframes.db'

        return url

    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '3306')
    user = os.environ.get('DB_USER', 'root')
    pw   = os.environ.get('DB_PASSWORD', '')
    name = os.environ.get('DB_NAME', 'railway')
    return f'mysql+pymysql://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4'


class BaseConfig:
    # Core
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-please-change-in-prod')
    TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Kolkata')

    # Database
    _uri = _db_uri()
    SQLALCHEMY_DATABASE_URI = _uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    if _uri.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {'check_same_thread': False},
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_recycle': 280,
            'pool_pre_ping': True,
            'connect_args': {'connect_timeout': 10},
        }

    # Uploads
    UPLOAD_FOLDER = os.path.abspath(os.environ.get('UPLOAD_FOLDER', 'uploads'))
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_MB', 500)) * 1024 * 1024

    ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'mkv', 'avi'}
    ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a'}
    ALLOWED_THUMB_EXTENSIONS  = {'jpg', 'jpeg', 'png', 'webp'}

    # Session
    PERMANENT_SESSION_LIFETIME   = timedelta(hours=24)
    SESSION_COOKIE_HTTPONLY      = True
    SESSION_COOKIE_SAMESITE      = 'Lax'
    SESSION_COOKIE_NAME          = 'nf_session'

    # Admin
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'NativeFrames@2024')

    # Rate limiting (simple in-memory store)
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_SECONDS = 300   # 5 minutes

    # WTF / CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


_configs = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}


def get_config(name: str = 'default'):
    return _configs.get(name, DevelopmentConfig)
