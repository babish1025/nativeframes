"""
NativeFrames — SQLAlchemy Models
All database tables defined here with relationships and indexes.
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Base Model
# ---------------------------------------------------------------------------
class BaseModel(db.Model):
    __abstract__ = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
class Admin(BaseModel):
    __tablename__ = 'admins'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name  = db.Column(db.String(150), nullable=True)
    created_at    = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    audit_logs = db.relationship('AdminAuditLog', back_populates='admin', lazy='dynamic')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Admin {self.username}>'


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
class Folder(BaseModel):
    __tablename__ = 'folders'

    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(200), nullable=False)
    description       = db.Column(db.Text, nullable=True)
    parent_id         = db.Column(db.Integer, db.ForeignKey('folders.id', ondelete='SET NULL'), nullable=True, index=True)
    visibility_status = db.Column(db.String(20), nullable=False, default='published')  # published | hidden
    sort_order        = db.Column(db.Integer, nullable=False, default=0)
    cover_image       = db.Column(db.String(500), nullable=True)
    created_at        = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at        = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    parent   = db.relationship('Folder', remote_side=[id], backref=db.backref('children', lazy='dynamic'))
    media    = db.relationship('Media', back_populates='folder', lazy='dynamic',
                               primaryjoin="and_(Media.folder_id==Folder.id, Media.deleted_at==None)")
    events   = db.relationship('MediaEvent', back_populates='folder', lazy='dynamic')

    @property
    def published_media_count(self):
        return self.media.filter_by(status='published').count()

    def __repr__(self):
        return f'<Folder {self.name}>'


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------
class Media(BaseModel):
    __tablename__ = 'media'

    id               = db.Column(db.Integer, primary_key=True)
    title            = db.Column(db.String(300), nullable=False)
    description      = db.Column(db.Text, nullable=True)
    caption          = db.Column(db.Text, nullable=True)
    tags             = db.Column(db.String(500), nullable=True)   # comma-separated
    media_type       = db.Column(db.String(20), nullable=False)   # photo | video | audio
    stored_filename  = db.Column(db.String(400), nullable=True)   # UUID-based filename
    storage_path     = db.Column(db.String(500), nullable=True)   # relative path under uploads/
    thumbnail_path   = db.Column(db.String(500), nullable=True)   # relative path under uploads/thumbnails/
    folder_id        = db.Column(db.Integer, db.ForeignKey('folders.id', ondelete='SET NULL'), nullable=True, index=True)
    status           = db.Column(db.String(20), nullable=False, default='draft', index=True)  # draft | published
    is_featured      = db.Column(db.Boolean, nullable=False, default=False)
    mime_type        = db.Column(db.String(100), nullable=True)
    file_size        = db.Column(db.BigInteger, nullable=True)     # bytes
    duration_seconds = db.Column(db.Float, nullable=True)
    artist           = db.Column(db.String(200), nullable=True)    # for audio
    view_count       = db.Column(db.Integer, nullable=False, default=0)
    like_count       = db.Column(db.Integer, nullable=False, default=0)
    created_at       = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at       = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    published_at     = db.Column(db.DateTime, nullable=True)
    deleted_at       = db.Column(db.DateTime, nullable=True)

    # Relationships
    folder     = db.relationship('Folder', back_populates='media',
                                 primaryjoin="and_(Media.folder_id==Folder.id)")
    events     = db.relationship('MediaEvent', back_populates='media', cascade='all, delete-orphan', lazy='dynamic')
    likes      = db.relationship('MediaLike', back_populates='media', cascade='all, delete-orphan', lazy='dynamic')
    favourites = db.relationship('MediaFavourite', back_populates='media', cascade='all, delete-orphan', lazy='dynamic')

    @property
    def file_path(self):
        return self.storage_path

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def tags_list(self):
        return [t.strip() for t in (self.tags or '').split(',') if t.strip()]

    @property
    def file_size_human(self):
        if not self.file_size:
            return '—'
        for unit in ('B', 'KB', 'MB', 'GB'):
            if self.file_size < 1024:
                return f'{self.file_size:.1f} {unit}'
            self.file_size /= 1024
        return f'{self.file_size:.1f} TB'

    def __repr__(self):
        return f'<Media {self.title} ({self.media_type})>'


# ---------------------------------------------------------------------------
# Viewer Sessions
# ---------------------------------------------------------------------------
class ViewerSession(BaseModel):
    __tablename__ = 'viewer_sessions'

    id              = db.Column(db.Integer, primary_key=True)
    display_name    = db.Column(db.String(150), nullable=False, index=True)
    normalized_name = db.Column(db.String(150), nullable=False, index=True)   # lowercase stripped
    session_token   = db.Column(db.String(128), unique=True, nullable=False, index=True)
    created_at      = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_activity_at= db.Column(db.DateTime, nullable=True)
    ended_at        = db.Column(db.DateTime, nullable=True)
    session_status  = db.Column(db.String(20), nullable=False, default='active')  # active | expired | ended
    ip_address      = db.Column(db.String(80), nullable=True)
    user_agent      = db.Column(db.String(300), nullable=True)

    events     = db.relationship('MediaEvent', back_populates='session', lazy='dynamic')
    likes      = db.relationship('MediaLike', back_populates='session', lazy='dynamic')
    favourites = db.relationship('MediaFavourite', back_populates='session', lazy='dynamic')

    def __repr__(self):
        return f'<ViewerSession {self.display_name} {self.session_token[:8]}>'


# ---------------------------------------------------------------------------
# Media Events (activity log)
# ---------------------------------------------------------------------------
class MediaEvent(BaseModel):
    __tablename__ = 'media_events'
    __table_args__ = (
        db.Index('ix_me_session_media', 'viewer_session_id', 'media_id'),
        db.Index('ix_me_event_type',    'event_type'),
        db.Index('ix_me_timestamp',     'event_timestamp'),
    )

    id                = db.Column(db.Integer, primary_key=True)
    viewer_session_id = db.Column(db.Integer, db.ForeignKey('viewer_sessions.id', ondelete='CASCADE'), nullable=True, index=True)
    media_id          = db.Column(db.Integer, db.ForeignKey('media.id', ondelete='SET NULL'), nullable=True, index=True)
    folder_id         = db.Column(db.Integer, db.ForeignKey('folders.id', ondelete='SET NULL'), nullable=True)
    event_type        = db.Column(db.String(50), nullable=False)
    # Possible: viewer_login, viewer_logout, gallery_open, folder_open,
    #           image_open, video_start, video_progress, video_complete,
    #           audio_start, audio_complete, like_add, like_remove,
    #           fav_add, fav_remove, download, admin_upload, admin_edit,
    #           admin_publish, admin_unpublish, admin_delete, admin_restore
    event_timestamp   = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    event_metadata    = db.Column(db.Text, nullable=True)   # JSON string, non-sensitive

    session = db.relationship('ViewerSession', back_populates='events')
    media   = db.relationship('Media', back_populates='events')
    folder  = db.relationship('Folder', back_populates='events')

    def __repr__(self):
        return f'<MediaEvent {self.event_type} @ {self.event_timestamp}>'


# ---------------------------------------------------------------------------
# Media Likes
# ---------------------------------------------------------------------------
class MediaLike(BaseModel):
    __tablename__  = 'media_likes'
    __table_args__ = (
        db.UniqueConstraint('viewer_session_id', 'media_id', name='uq_like_session_media'),
    )

    id                = db.Column(db.Integer, primary_key=True)
    viewer_session_id = db.Column(db.Integer, db.ForeignKey('viewer_sessions.id', ondelete='CASCADE'), nullable=False)
    media_id          = db.Column(db.Integer, db.ForeignKey('media.id', ondelete='CASCADE'), nullable=False)
    created_at        = db.Column(db.DateTime, nullable=False, default=utcnow)

    session = db.relationship('ViewerSession', back_populates='likes')
    media   = db.relationship('Media', back_populates='likes')


# ---------------------------------------------------------------------------
# Media Favourites
# ---------------------------------------------------------------------------
class MediaFavourite(BaseModel):
    __tablename__  = 'media_favourites'
    __table_args__ = (
        db.UniqueConstraint('viewer_session_id', 'media_id', name='uq_fav_session_media'),
    )

    id                = db.Column(db.Integer, primary_key=True)
    viewer_session_id = db.Column(db.Integer, db.ForeignKey('viewer_sessions.id', ondelete='CASCADE'), nullable=False)
    media_id          = db.Column(db.Integer, db.ForeignKey('media.id', ondelete='CASCADE'), nullable=False)
    created_at        = db.Column(db.DateTime, nullable=False, default=utcnow)

    session = db.relationship('ViewerSession', back_populates='favourites')
    media   = db.relationship('Media', back_populates='favourites')


# ---------------------------------------------------------------------------
# App Settings
# ---------------------------------------------------------------------------
class AppSetting(BaseModel):
    __tablename__ = 'app_settings'

    key        = db.Column(db.String(80), primary_key=True)
    value      = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Keys and defaults:
    # allow_likes         = '1'
    # allow_favourites    = '1'
    # allow_downloads     = '0'
    # allow_comments      = '0'
    # allow_share_links   = '0'
    # show_view_counts    = '0'
    # gallery_title       = 'NativeFrames Gallery'
    # gallery_subtitle    = 'Every frame tells a story.'
    # items_per_page      = '24'

    def __repr__(self):
        return f'<AppSetting {self.key}={self.value}>'


# ---------------------------------------------------------------------------
# Admin Audit Logs
# ---------------------------------------------------------------------------
class AdminAuditLog(BaseModel):
    __tablename__ = 'admin_audit_logs'

    id          = db.Column(db.Integer, primary_key=True)
    admin_id    = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='SET NULL'), nullable=True)
    action      = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)   # media | folder | setting | auth
    entity_id   = db.Column(db.Integer, nullable=True)
    details     = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    admin = db.relationship('Admin', back_populates='audit_logs')

    def __repr__(self):
        return f'<AdminAuditLog {self.action} @ {self.created_at}>'
