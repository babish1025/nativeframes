"""
NativeFrames — API Routes (AJAX endpoints)
"""
import json
from flask import Blueprint, request, jsonify, session, g, abort

from ..models import (db, Media, ViewerSession, MediaLike,
                      MediaFavourite, MediaEvent)
from ..utils  import (viewer_required, log_event, utcnow,
                      setting_enabled, get_setting)

api_bp = Blueprint('api', __name__)


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
