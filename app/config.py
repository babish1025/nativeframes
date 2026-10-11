"""
NativeFrames — Application Configuration
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _db_uri():
    """
    Build the SQLAlchemy database URI.

    Priority order (first match wins):
      1. USE_SQLITE=1           → local SQLite (dev/testing only)
      2. DATABASE_URL           → use as-is (any valid SQLAlchemy URL)
      3. Railway TCP proxy vars → MYSQLUSER + MYSQLPASSWORD +
                                  RAILWAY_TCP_PROXY_DOMAIN + RAILWAY_TCP_PROXY_PORT +
                                  MYSQLDATABASE   (copy these 5 from Railway → Vercel)
      4. Generic DB_* vars      → DB_HOST + DB_PORT + DB_USER + DB_PASSWORD + DB_NAME
      5. Fallback                → SQLite on /tmp (Vercel-safe cold-start)
    """
    if os.environ.get('USE_SQLITE', '').lower() in ('1', 'true'):
        return 'sqlite:////tmp/nativeframes.db'

    # --- Priority 2: explicit DATABASE_URL ---
    url = os.environ.get('DATABASE_URL', '')
    if url:
        if url.startswith('sqlite:'):
            return url
        # Normalise driver name
        if url.startswith('mysql://'):
            url = url.replace('mysql://', 'mysql+pymysql://', 1)
        # Railway internal hostname is not reachable from Vercel
        if 'railway.internal' in url:
            import socket
            try:
                socket.gethostbyname('mysql.railway.internal')
            except (socket.gaierror, OSError):
                return 'sqlite:////tmp/nativeframes.db'
        return url

    # --- Priority 3: Railway TCP proxy individual vars ---
    # Copy these five vars from Railway dashboard → Vercel Environment Variables
    rly_host = os.environ.get('RAILWAY_TCP_PROXY_DOMAIN', '')
    rly_port = os.environ.get('RAILWAY_TCP_PROXY_PORT', '')
    rly_user = os.environ.get('MYSQLUSER', '')
    rly_pw   = os.environ.get('MYSQLPASSWORD', '')
    rly_db   = os.environ.get('MYSQLDATABASE', 'railway')
    if rly_host and rly_port and rly_user:
        return (
            f'mysql+pymysql://{rly_user}:{rly_pw}'
            f'@{rly_host}:{rly_port}/{rly_db}?charset=utf8mb4'
        )

    # --- Priority 4: generic DB_* vars ---
    host = os.environ.get('DB_HOST', '')
    if host and host not in ('localhost', '127.0.0.1'):
        port = os.environ.get('DB_PORT', '3306')
        user = os.environ.get('DB_USER', 'root')
        pw   = os.environ.get('DB_PASSWORD', '')
        name = os.environ.get('DB_NAME', 'railway')
        return f'mysql+pymysql://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4'

    # --- Priority 5: safe SQLite fallback ---
    return 'sqlite:////tmp/nativeframes.db'




def _upload_folder():
    """
    Determine the upload directory.
    Vercel/serverless environments have a strictly read-only filesystem except /tmp.
    """
    is_serverless = (
        bool(os.environ.get('VERCEL'))
        or bool(os.environ.get('VERCEL_ENV'))
        or bool(os.environ.get('VERCEL_URL'))
        or bool(os.environ.get('VERCEL_REGION'))
        or bool(os.environ.get('NOW_REGION'))
        or bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
        or bool(os.environ.get('LAMBDA_TASK_ROOT'))
        or os.path.abspath('.').startswith('/var/task')
    )

    custom = os.environ.get('UPLOAD_FOLDER')
    if is_serverless:
        # On serverless (Vercel / AWS Lambda), the entire filesystem is read-only except /tmp
        if custom and custom.startswith('/tmp'):
            return custom
        return '/tmp/uploads'

    if custom:
        return os.path.abspath(custom)
    return os.path.abspath('uploads')


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

    # Uploads — use /tmp on serverless (Vercel fs is read-only except /tmp)
    UPLOAD_FOLDER = _upload_folder()
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
