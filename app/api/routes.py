"""
NativeFrames — API Routes (AJAX endpoints)
"""
import json
from flask import Blueprint, request, jsonify, session, g, abort

from sqlalchemy import desc

from ..models import (db, Media, Folder, ViewerSession, MediaLike,
                      MediaFavourite, MediaEvent)
from ..utils  import (viewer_required, admin_required, log_event, utcnow,
                      setting_enabled, get_setting)

api_bp = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# Folders — Admin JSON API
# ---------------------------------------------------------------------------
@api_bp.route('/folders', methods=['GET'])
@admin_required
def list_folders():
    """
    Return all folders as JSON for admin dropdowns and folder pickers.
    GET /api/folders
    Response: { "success": true, "folders": [{"id": 1, "name": "...", "parent_id": null}] }
    """
    try:
        folders = Folder.query.order_by(Folder.sort_order, Folder.name).all()
        return jsonify({
            'success': True,
            'folders': [
                {
                    'id':         f.id,
                    'name':       f.name,
                    'parent_id':  f.parent_id,
                    'visibility': f.visibility_status,
                }
                for f in folders
            ],
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc), 'folders': []}), 500


def _get_vs():
    token = session.get('viewer_token')
    if not token:
        return None
    return ViewerSession.query.filter_by(session_token=token, session_status='active').first()


# ---------------------------------------------------------------------------
# Like toggle
# ---------------------------------------------------------------------------
@api_bp.route('/like/<int:media_id>', methods=['POST'])
def toggle_like(media_id):
    if not setting_enabled('allow_likes'):
        return jsonify({'error': 'Likes are disabled.'}), 403

    vs = _get_vs()
    if not vs:
        return jsonify({'error': 'Not authenticated.'}), 401

    media = Media.query.filter_by(id=media_id, status='published').filter(Media.deleted_at == None).first()
    if not media:
        return jsonify({'error': 'Media not found.'}), 404

    existing = MediaLike.query.filter_by(viewer_session_id=vs.id, media_id=media_id).first()
    if existing:
        db.session.delete(existing)
        media.like_count = max(0, (media.like_count or 0) - 1)
        db.session.commit()
        log_event('like_remove', media_id=media_id)
        return jsonify({'liked': False, 'count': media.like_count})
    else:
        like = MediaLike(viewer_session_id=vs.id, media_id=media_id)
        db.session.add(like)
        media.like_count = (media.like_count or 0) + 1
        db.session.commit()
        log_event('like_add', media_id=media_id)
        return jsonify({'liked': True, 'count': media.like_count})


# ---------------------------------------------------------------------------
# Favourite toggle
# ---------------------------------------------------------------------------
@api_bp.route('/favourite/<int:media_id>', methods=['POST'])
def toggle_favourite(media_id):
    if not setting_enabled('allow_favourites'):
        return jsonify({'error': 'Favourites are disabled.'}), 403

    vs = _get_vs()
    if not vs:
        return jsonify({'error': 'Not authenticated.'}), 401

    media = Media.query.filter_by(id=media_id, status='published').filter(Media.deleted_at == None).first()
    if not media:
        return jsonify({'error': 'Media not found.'}), 404

    existing = MediaFavourite.query.filter_by(viewer_session_id=vs.id, media_id=media_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        log_event('fav_remove', media_id=media_id)
        return jsonify({'favourited': False})
    else:
        fav = MediaFavourite(viewer_session_id=vs.id, media_id=media_id)
        db.session.add(fav)
        db.session.commit()
        log_event('fav_add', media_id=media_id)
        return jsonify({'favourited': True})


# ---------------------------------------------------------------------------
# Log playback event
# ---------------------------------------------------------------------------
@api_bp.route('/event', methods=['POST'])
def log_viewer_event():
    vs = _get_vs()
    if not vs:
        return jsonify({'error': 'Not authenticated.'}), 401

    data       = request.get_json(silent=True) or {}
    event_type = data.get('event_type', '')
    media_id   = data.get('media_id')
    folder_id  = data.get('folder_id')
    meta       = data.get('meta', {})

    # Whitelist accepted event types
    ALLOWED_TYPES = {
        'video_start', 'video_progress', 'video_complete',
        'audio_start', 'audio_complete', 'image_open',
        'gallery_open', 'folder_open', 'download',
    }
    if event_type not in ALLOWED_TYPES:
        return jsonify({'error': 'Unknown event type.'}), 400

    # Update last_activity on session
    vs.last_activity_at = utcnow()

    event = MediaEvent(
        viewer_session_id = vs.id,
        media_id          = media_id,
        folder_id         = folder_id,
        event_type        = event_type,
        event_metadata    = json.dumps(meta) if meta else None,
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Download — only if enabled
# ---------------------------------------------------------------------------
@api_bp.route('/download/<int:media_id>')
def download_media(media_id):
    if not setting_enabled('allow_downloads'):
        abort(403)

    vs = _get_vs()
    if not vs:
        abort(401)

    media = Media.query.filter_by(id=media_id, status='published').filter(Media.deleted_at == None).first_or_404()

    import os
    from flask import current_app, send_from_directory
    upload_dir = current_app.config['UPLOAD_FOLDER']
    if not media.storage_path:
        abort(404)

    log_event('download', media_id=media_id)
    parts = media.storage_path.split('/', 1)
    if len(parts) == 2:
        return send_from_directory(
            os.path.join(upload_dir, parts[0]),
            parts[1],
            as_attachment=True,
            download_name=media.stored_filename,
        )
    return send_from_directory(upload_dir, media.storage_path, as_attachment=True)


# ---------------------------------------------------------------------------
# Gallery Folders — Viewer JSON API
# ---------------------------------------------------------------------------
@api_bp.route('/gallery/folders', methods=['GET'])
def get_gallery_folders():
    """
    Return published folders with counts and thumbnails for viewer gallery navigation.
    GET /api/gallery/folders?parent_id=X
    """
    try:
        parent_id = request.args.get('parent_id')
        q = Folder.query.filter_by(visibility_status='published')
        if parent_id is not None:
            if parent_id == '' or parent_id.lower() == 'null':
                q = q.filter_by(parent_id=None)
            elif parent_id.isdigit():
                q = q.filter_by(parent_id=int(parent_id))
        else:
            # Default to top-level published folders
            q = q.filter_by(parent_id=None)

        folders = q.order_by(Folder.sort_order, Folder.name).all()
        return jsonify({
            'success': True,
            'folders': [
                {
                    'id':               f.id,
                    'name':             f.name,
                    'description':      f.description,
                    'parent_id':        f.parent_id,
                    'cover_image':      f.get_cover_thumbnail_url(),
                    'photos_count':     f.published_photos_count,
                    'videos_count':     f.published_videos_count,
                    'audio_count':      f.published_audio_count,
                    'subfolders_count': f.published_subfolders_count,
                }
                for f in folders
            ]
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc), 'folders': []}), 500


# ---------------------------------------------------------------------------
# Gallery Media — Viewer JSON API filtered by folder
# ---------------------------------------------------------------------------
@api_bp.route('/gallery/media', methods=['GET'])
def get_gallery_media():
    """
    Return published media scoped strictly to a folder ID and optional media type.
    GET /api/gallery/media?folder_id=1&type=video
    """
    try:
        folder_id   = request.args.get('folder_id', type=int)
        filter_type = request.args.get('type', '').strip().lower()
        page        = request.args.get('page', 1, type=int)
        per_page    = request.args.get('per_page', 24, type=int)

        q = Media.query.filter_by(status='published').filter(Media.deleted_at == None)

        if folder_id is not None:
            q = q.filter(Media.folder_id == folder_id)

        if filter_type in ('photos', 'photo'):
            q = q.filter(Media.media_type == 'photo')
        elif filter_type in ('videos', 'video'):
            q = q.filter(Media.media_type == 'video')
        elif filter_type in ('audio', 'music'):
            q = q.filter(Media.media_type == 'audio')

        q = q.order_by(desc(Media.published_at), desc(Media.created_at))
        pagination = q.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'folder_id': folder_id,
            'total': pagination.total,
            'page': pagination.page,
            'pages': pagination.pages,
            'media': [
                {
                    'id':             m.id,
                    'title':          m.title,
                    'media_type':     m.media_type,
                    'folder_id':      m.folder_id,
                    'storage_path':   m.storage_path,
                    'thumbnail_path': m.thumbnail_path,
                    'duration_seconds': m.duration_seconds,
                    'view_count':     m.view_count,
                    'like_count':     m.like_count,
                }
                for m in pagination.items
            ]
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc), 'media': []}), 500

