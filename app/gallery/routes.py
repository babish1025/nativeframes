"""
NativeFrames — Gallery Routes (Viewer-facing)
Folder-based media navigation, subfolders, category filters, and viewer media player.
"""
import json
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, abort, g, current_app, flash)
from sqlalchemy import desc, or_

from ..models import (db, Media, Folder, ViewerSession, MediaEvent,
                      MediaLike, MediaFavourite, AboutItem)
from ..utils  import (viewer_required, log_event, utcnow,
                      format_duration, get_setting, setting_enabled,
                      get_settings_dict)

gallery_bp = Blueprint('gallery', __name__)


def _get_about_items():
    """Return active About Us items ordered by sort_order."""
    try:
        return AboutItem.query.filter_by(is_active=True).order_by(AboutItem.sort_order, AboutItem.id).all()
    except Exception:
        return []


def _get_viewer_session():
    token = session.get('viewer_token')
    if not token:
        return None
    return ViewerSession.query.filter_by(session_token=token, session_status='active').first()


def get_folder_breadcrumbs(folder, active_type=None):
    """
    Build breadcrumb hierarchy:
    Home > Events > College Day > Videos (if active_type is set and not 'all')
    """
    crumbs = [{'name': 'Home', 'url': url_for('gallery.index')}]
    ancestors = []
    curr = folder.parent
    while curr:
        ancestors.append(curr)
        curr = curr.parent

    for ancestor in reversed(ancestors):
        crumbs.append({
            'name': ancestor.name,
            'url': url_for('gallery.folder_view', folder_id=ancestor.id),
        })

    type_labels = {
        'photo': 'Photos',
        'photos': 'Photos',
        'video': 'Videos',
        'videos': 'Videos',
        'audio': 'Audio',
        'music': 'Audio',
    }

    if active_type and active_type in type_labels:
        crumbs.append({
            'name': folder.name,
            'url': url_for('gallery.folder_view', folder_id=folder.id),
        })
        crumbs.append({
            'name': type_labels[active_type],
            'url': None,
        })
    else:
        crumbs.append({
            'name': folder.name,
            'url': None,
        })

    return crumbs


class UnfiledFolder:
    def __init__(self):
        self.id = 0
        self.name = "General Media"
        self.description = "Direct uploads and unfiled media items"
        self.parent_id = None
        self.parent = None
        self.visibility_status = 'published'

    def get_cover_thumbnail_url(self):
        item = (Media.query.filter_by(status='published', folder_id=None, deleted_at=None)
                .order_by(desc(Media.published_at), desc(Media.created_at)).first())
        if item:
            return item.thumbnail_path or item.storage_path
        return None

    @property
    def published_photos_count(self):
        return Media.query.filter_by(status='published', folder_id=None, deleted_at=None, media_type='photo').count()

    @property
    def published_videos_count(self):
        return Media.query.filter_by(status='published', folder_id=None, deleted_at=None, media_type='video').count()

    @property
    def published_audio_count(self):
        return Media.query.filter_by(status='published', folder_id=None, deleted_at=None, media_type='audio').count()

    @property
    def published_subfolders_count(self):
        return 0


# ---------------------------------------------------------------------------
# Gallery Index — Folder-Based Viewer Home
# ---------------------------------------------------------------------------
@gallery_bp.route('/')
@viewer_required
def index():
    vs  = g.viewer_session
    cfg = get_settings_dict()

    page     = request.args.get('page', 1, type=int)
    per_page = int(cfg.get('items_per_page', 24))
    search   = request.args.get('q', '').strip()
    tab      = request.args.get('tab', 'folders')

    # If viewer searched for media
    if search:
        q = (Media.query
             .filter_by(status='published')
             .filter(Media.deleted_at == None))
        q = q.filter(or_(
            Media.title.ilike(f'%{search}%'),
            Media.description.ilike(f'%{search}%'),
            Media.tags.ilike(f'%{search}%'),
        ))
        q = q.order_by(desc(Media.published_at), desc(Media.created_at))
        pagination = q.paginate(page=page, per_page=per_page, error_out=False)
        fav_ids  = {f.media_id for f in vs.favourites.all()} if setting_enabled('allow_favourites') else set()
        like_ids = {l.media_id for l in vs.likes.all()} if setting_enabled('allow_likes') else set()
        return render_template('gallery/index.html',
            is_search=True,
            is_folder_home=False,
            is_favourites=False,
            media=pagination.items,
            pagination=pagination,
            search=search,
            tab='search',
            fav_ids=fav_ids,
            like_ids=like_ids,
            cfg=cfg,
            format_duration=format_duration,
            viewer_name=vs.display_name,
            about_items=_get_about_items(),
        )

    # If viewer clicked favourites tab
    if tab == 'favourites' and setting_enabled('allow_favourites'):
        fav_ids_list = [f.media_id for f in vs.favourites.all()]
        q = (Media.query
             .filter_by(status='published')
             .filter(Media.deleted_at == None))
        q = q.filter(Media.id.in_(fav_ids_list)) if fav_ids_list else q.filter(Media.id == None)
        q = q.order_by(desc(Media.published_at), desc(Media.created_at))
        pagination = q.paginate(page=page, per_page=per_page, error_out=False)
        fav_ids  = set(fav_ids_list)
        like_ids = {l.media_id for l in vs.likes.all()} if setting_enabled('allow_likes') else set()
        return render_template('gallery/index.html',
            is_favourites=True,
            is_folder_home=False,
            is_search=False,
            media=pagination.items,
            pagination=pagination,
            search='',
            tab='favourites',
            fav_ids=fav_ids,
            like_ids=like_ids,
            cfg=cfg,
            format_duration=format_duration,
            viewer_name=vs.display_name,
            about_items=_get_about_items(),
        )

    # DEFAULT VIEW: FOLDER-BASED GALLERY HOME
    # Do not display all media automatically!
    top_folders = (Folder.query
                   .filter_by(visibility_status='published', parent_id=None)
                   .order_by(Folder.sort_order, Folder.name).all())

    # Include any orphaned published folders (parent_id is set but parent does not exist or is hidden)
    all_published = Folder.query.filter_by(visibility_status='published').all()
    pub_ids = {f.id for f in all_published}
    orphans = [f for f in all_published if f.parent_id is not None and f.parent_id not in pub_ids]
    folders = list(top_folders) + orphans

    # If there are any unassigned published media items, include General Media folder
    unfiled_count = Media.query.filter_by(status='published', folder_id=None).filter(Media.deleted_at == None).count()
    if unfiled_count > 0:
        folders.append(UnfiledFolder())

    if page == 1:
        log_event('gallery_open')

    return render_template('gallery/index.html',
        folders=folders,
        is_folder_home=True,
        is_search=False,
        is_favourites=False,
        media=[],
        search='',
        tab='folders',
        cfg=cfg,
        format_duration=format_duration,
        viewer_name=vs.display_name,
        about_items=_get_about_items(),
    )


# ---------------------------------------------------------------------------
# Folder View — Subfolders & Scoped Media
# ---------------------------------------------------------------------------
@gallery_bp.route('/folder/<int:folder_id>')
@viewer_required
def folder_view(folder_id):
    vs  = g.viewer_session
    cfg = get_settings_dict()

    if folder_id == 0:
        folder = UnfiledFolder()
        sub_folders = []
        q = (Media.query
             .filter_by(status='published', folder_id=None)
             .filter(Media.deleted_at == None))
        base_counts = (Media.query
                       .filter_by(status='published', folder_id=None)
                       .filter(Media.deleted_at == None))
    else:
        folder = Folder.query.filter_by(id=folder_id, visibility_status='published').first_or_404()
        sub_folders = (Folder.query
                       .filter_by(parent_id=folder_id, visibility_status='published')
                       .order_by(Folder.sort_order, Folder.name).all())
        q = (Media.query
             .filter_by(status='published', folder_id=folder_id)
             .filter(Media.deleted_at == None))
        base_counts = (Media.query
                       .filter_by(status='published', folder_id=folder_id)
                       .filter(Media.deleted_at == None))

    page        = request.args.get('page', 1, type=int)
    per_page    = int(cfg.get('items_per_page', 24))
    search      = request.args.get('q', '').strip()
    filter_type = request.args.get('type') or request.args.get('tab', 'all')
    filter_type = filter_type.strip().lower()

    # Subfolders assigned to this folder
    sub_folders = (Folder.query
                   .filter_by(parent_id=folder_id, visibility_status='published')
                   .order_by(Folder.sort_order, Folder.name).all())

    # Media query: strictly filtered by this folder ID!
    q = (Media.query
         .filter_by(status='published', folder_id=folder_id)
         .filter(Media.deleted_at == None))

    if search:
        q = q.filter(or_(
            Media.title.ilike(f'%{search}%'),
            Media.description.ilike(f'%{search}%'),
            Media.tags.ilike(f'%{search}%'),
        ))

    # Media category filters: All, Photos, Videos, Audio
    if filter_type in ('photos', 'photo'):
        q = q.filter(Media.media_type == 'photo')
    elif filter_type in ('videos', 'video'):
        q = q.filter(Media.media_type == 'video')
    elif filter_type in ('audio', 'music'):
        q = q.filter(Media.media_type == 'audio')
    else:
        filter_type = 'all'

    q = q.order_by(desc(Media.published_at), desc(Media.created_at))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    # Scoped media counts for the category tabs inside this folder
    base_counts = (Media.query
                   .filter_by(status='published', folder_id=folder_id)
                   .filter(Media.deleted_at == None))
    if search:
        base_counts = base_counts.filter(or_(
            Media.title.ilike(f'%{search}%'),
            Media.description.ilike(f'%{search}%'),
            Media.tags.ilike(f'%{search}%'),
        ))
    total_count  = base_counts.count()
    photos_count = base_counts.filter(Media.media_type == 'photo').count()
    videos_count = base_counts.filter(Media.media_type == 'video').count()
    audio_count  = base_counts.filter(Media.media_type == 'audio').count()

    # Breadcrumbs (e.g. Home > Events > College Day > Videos)
    breadcrumbs = get_folder_breadcrumbs(folder, active_type=filter_type)

    fav_ids  = {f.media_id for f in vs.favourites.all()} if setting_enabled('allow_favourites') else set()
    like_ids = {l.media_id for l in vs.likes.all()} if setting_enabled('allow_likes') else set()

    log_event('folder_open', folder_id=folder_id, meta={'name': folder.name})

    return render_template('gallery/folder.html',
        folder=folder,
        sub_folders=sub_folders,
        media=pagination.items,
        pagination=pagination,
        search=search,
        filter_type=filter_type,
        total_count=total_count,
        photos_count=photos_count,
        videos_count=videos_count,
        audio_count=audio_count,
        breadcrumbs=breadcrumbs,
        cfg=cfg,
        fav_ids=fav_ids,
        like_ids=like_ids,
        format_duration=format_duration,
        viewer_name=vs.display_name,
        about_items=_get_about_items(),
    )


# ---------------------------------------------------------------------------
# Individual Media Viewer
# ---------------------------------------------------------------------------
@gallery_bp.route('/media/<int:media_id>')
@viewer_required
def media_view(media_id):
    vs  = g.viewer_session
    cfg = get_settings_dict()
    media = (Media.query
             .filter_by(id=media_id, status='published')
             .filter(Media.deleted_at == None)
             .first_or_404())

    # Increment view count
    media.view_count += 1
    db.session.commit()

    # Log event
    event_map = {'photo': 'image_open', 'video': 'video_start', 'audio': 'audio_start'}
    log_event(event_map.get(media.media_type, 'image_open'), media_id=media.id)

    # Prev/next in same folder or globally
    q_base = (Media.query
              .filter_by(status='published')
              .filter(Media.deleted_at == None)
              .filter(Media.media_type == media.media_type))
    if media.folder_id:
        q_base = q_base.filter(Media.folder_id == media.folder_id)

    all_ids = [m.id for m in q_base.order_by(desc(Media.published_at)).all()]
    idx     = all_ids.index(media.id) if media.id in all_ids else -1
    prev_id = all_ids[idx - 1] if idx > 0 else None
    next_id = all_ids[idx + 1] if idx < len(all_ids) - 1 else None

    fav_ids  = {f.media_id for f in vs.favourites.all()} if setting_enabled('allow_favourites') else set()
    like_ids = {l.media_id for l in vs.likes.all()} if setting_enabled('allow_likes') else set()

    return render_template('gallery/media_view.html',
        media=media, cfg=cfg,
        prev_id=prev_id, next_id=next_id,
        fav_ids=fav_ids, like_ids=like_ids,
        format_duration=format_duration,
        viewer_name=vs.display_name,
        about_items=_get_about_items(),
    )
