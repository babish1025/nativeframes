"""
NativeFrames — Gallery Routes (Viewer-facing)
"""
import json
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, abort, g, current_app, flash)
from sqlalchemy import desc, or_

from ..models import (db, Media, Folder, ViewerSession, MediaEvent,
                      MediaLike, MediaFavourite)
from ..utils  import (viewer_required, log_event, utcnow,
                      format_duration, get_setting, setting_enabled,
                      get_settings_dict)

gallery_bp = Blueprint('gallery', __name__)


def _get_viewer_session():
    token = session.get('viewer_token')
    if not token:
        return None
    return ViewerSession.query.filter_by(session_token=token, session_status='active').first()


# ---------------------------------------------------------------------------
# Gallery index
# ---------------------------------------------------------------------------
@gallery_bp.route('/')
@viewer_required
def index():
    vs  = g.viewer_session
    cfg = get_settings_dict()

    page        = request.args.get('page', 1, type=int)
    per_page    = int(cfg.get('items_per_page', 24))
    search      = request.args.get('q', '').strip()
    filter_type = request.args.get('type', '')
    filter_folder = request.args.get('folder_id', '', type=str)
    tab         = request.args.get('tab', 'all')  # all|photos|videos|audio|folders|favourites

    # Base query: published, not deleted
    q = Media.query.filter_by(status='published').filter(Media.deleted_at == None)

    if search:
        q = q.filter(or_(
            Media.title.ilike(f'%{search}%'),
            Media.description.ilike(f'%{search}%'),
            Media.tags.ilike(f'%{search}%'),
        ))

    if tab == 'photos':
        q = q.filter(Media.media_type == 'photo')
    elif tab == 'videos':
        q = q.filter(Media.media_type == 'video')
    elif tab == 'audio':
        q = q.filter(Media.media_type == 'audio')
    elif tab == 'favourites' and setting_enabled('allow_favourites'):
        fav_ids = [f.media_id for f in vs.favourites.all()]
        q = q.filter(Media.id.in_(fav_ids)) if fav_ids else q.filter(Media.id == None)

    if filter_folder.isdigit():
        folder = Folder.query.filter_by(id=int(filter_folder), visibility_status='published').first()
        if folder:
            q = q.filter(Media.folder_id == int(filter_folder))
            log_event('folder_open', folder_id=int(filter_folder))

    q = q.order_by(desc(Media.published_at), desc(Media.created_at))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    # Published folders for navigation
    folders = (Folder.query
               .filter_by(visibility_status='published')
               .order_by(Folder.sort_order, Folder.name).all())

    # Favourite IDs for this session
    fav_ids  = {f.media_id for f in vs.favourites.all()} if setting_enabled('allow_favourites') else set()
    like_ids = {l.media_id for l in vs.likes.all()} if setting_enabled('allow_likes') else set()

    # Log gallery open (once per page load)
    if page == 1 and not search and not filter_type:
        log_event('gallery_open')

    return render_template('gallery/index.html',
        media=pagination.items, pagination=pagination,
        folders=folders, search=search, tab=tab,
        filter_folder=filter_folder,
        fav_ids=fav_ids, like_ids=like_ids,
        cfg=cfg,
        format_duration=format_duration,
        viewer_name=vs.display_name,
    )


# ---------------------------------------------------------------------------
# Folder view
# ---------------------------------------------------------------------------
@gallery_bp.route('/folder/<int:folder_id>')
@viewer_required
def folder_view(folder_id):
    vs  = g.viewer_session
    cfg = get_settings_dict()
    folder = Folder.query.filter_by(id=folder_id, visibility_status='published').first_or_404()

    page       = request.args.get('page', 1, type=int)
    per_page   = int(cfg.get('items_per_page', 24))
    search     = request.args.get('q', '').strip()

    q = (Media.query
         .filter_by(status='published', folder_id=folder_id)
         .filter(Media.deleted_at == None))
    if search:
        q = q.filter(or_(
            Media.title.ilike(f'%{search}%'),
            Media.description.ilike(f'%{search}%'),
        ))
    q = q.order_by(desc(Media.published_at))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    # Subfolder navigation
    sub_folders = (Folder.query
                   .filter_by(parent_id=folder_id, visibility_status='published')
                   .order_by(Folder.sort_order, Folder.name).all())

    fav_ids  = {f.media_id for f in vs.favourites.all()} if setting_enabled('allow_favourites') else set()
    like_ids = {l.media_id for l in vs.likes.all()} if setting_enabled('allow_likes') else set()

    log_event('folder_open', folder_id=folder_id, meta={'name': folder.name})

    return render_template('gallery/folder.html',
        folder=folder, sub_folders=sub_folders,
        media=pagination.items, pagination=pagination,
        search=search, cfg=cfg,
        fav_ids=fav_ids, like_ids=like_ids,
        format_duration=format_duration,
        viewer_name=vs.display_name,
    )


# ---------------------------------------------------------------------------
# Individual media viewer
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
    )
