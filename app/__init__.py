"""
NativeFrames — Flask Application Factory
"""
import os
import logging
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from .config import get_config
from .models import db, Admin, AppSetting


csrf = CSRFProtect()
logger = logging.getLogger('nativeframes')


def create_app(env: str = 'default') -> Flask:
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
        static_url_path='/static',
    )

    # Load config
    cfg = get_config(env)
    app.config.from_object(cfg)

    # Logging
    logging.basicConfig(
        level=logging.DEBUG if app.config.get('DEBUG') else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    # Extensions
    db.init_app(app)
    csrf.init_app(app)

    # Ensure upload directories exist
    _ensure_upload_dirs(app)

    # Blueprints
    from .auth.routes   import auth_bp
    from .admin.routes  import admin_bp
    from .gallery.routes import gallery_bp
    from .api.routes    import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,  url_prefix='/admin')
    app.register_blueprint(gallery_bp, url_prefix='/gallery')
    app.register_blueprint(api_bp,    url_prefix='/api')

    # Init DB and seed
    with app.app_context():
        try:
            db.create_all()
            _seed_defaults(app)
            logger.info('Database ready.')
        except Exception as exc:
            logger.error('Database init failed: %s', exc)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def too_large(e):
        return render_template('errors/413.html'), 413

    # Welcome route
    from flask import redirect, url_for, session, request
    @app.route('/')
    def index():
        return render_template('index.html')

    # Media file serving (auth-protected)
    from flask import send_from_directory, abort
    @app.route('/uploads/<path:filename>', endpoint='uploaded_file')
    def uploaded_file(filename):
        # Viewers must be logged in; admins always allowed
        if not session.get('admin_logged') and not session.get('viewer_token'):
            abort(403)
        upload_dir = app.config.get('UPLOAD_FOLDER', 'uploads')
        if not os.path.exists(os.path.join(upload_dir, filename)):
            if os.path.exists(os.path.join('/tmp/uploads', filename)):
                upload_dir = '/tmp/uploads'
            elif os.path.exists(os.path.join(os.path.abspath('uploads'), filename)):
                upload_dir = os.path.abspath('uploads')
        return send_from_directory(upload_dir, filename)

    return app


def _ensure_upload_dirs(app: Flask):
    """Create upload subdirectories. Silently skips on read-only filesystems (e.g. Vercel)."""
    base = app.config.get('UPLOAD_FOLDER', 'uploads')
    if base.startswith('/var/task'):
        base = '/tmp/uploads'
        app.config['UPLOAD_FOLDER'] = base
    for sub in ('photos', 'videos', 'audio', 'thumbnails'):
        path = os.path.join(base, sub)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            if base != '/tmp/uploads':
                app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
                try:
                    os.makedirs(os.path.join('/tmp/uploads', sub), exist_ok=True)
                except OSError:
                    pass


def _seed_defaults(app: Flask):
    """Create default admin account and app settings if they don't exist."""
    # Default admin
    admin = Admin.query.first()
    if not admin:
        admin = Admin(
            username     = app.config['ADMIN_USERNAME'],
            display_name = 'Native Frames Admin',
        )
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)
        db.session.commit()
        logger.info('Default admin account created: %s', app.config['ADMIN_USERNAME'])
    else:
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.commit()
        logger.info('Admin password synchronized with configuration.')

    # Default settings
    defaults = {
        'allow_likes':       '1',
        'allow_favourites':  '1',
        'allow_downloads':   '0',
        'allow_comments':    '0',
        'allow_share_links': '0',
        'show_view_counts':  '0',
        'gallery_title':     'Native Frames Gallery',
        'gallery_subtitle':  'Every frame tells a story.',
        'items_per_page':    '24',
    }
    for key, val in defaults.items():
        if not AppSetting.query.get(key):
            db.session.add(AppSetting(key=key, value=val))
    db.session.commit()
