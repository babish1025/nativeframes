"""
NativeFrames — Admin Routes
Complete admin portal: dashboard, media, folders, viewers, analytics, settings, trash.
"""
import os
import json
from datetime import datetime, timedelta, timezone
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, current_app, jsonify, send_from_directory,
                   abort, g)
from sqlalchemy import func, desc, asc, and_, or_
from werkzeug.utils import secure_filename

from ..models import (db, Admin, Media, Folder, ViewerSession, MediaEvent,
                      MediaLike, MediaFavourite, AppSetting, AdminAuditLog)
from ..utils  import (admin_required, save_upload, delete_file_safe,
                      generate_image_thumbnail, audit_log, utcnow,
                      human_filesize, format_duration, get_settings_dict,
                      get_setting, allowed_file)

admin_bp = Blueprint('admin', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _allowed_image(f): return allowed_file(f.filename, current_app.config['ALLOWED_IMAGE_EXTENSIONS'])
def _allowed_video(f): return allowed_file(f.filename, current_app.config['ALLOWED_VIDEO_EXTENSIONS'])
def _allowed_audio(f): return allowed_file(f.filename, current_app.config['ALLOWED_AUDIO_EXTENSIONS'])
def _allowed_thumb(f): return allowed_file(f.filename, current_app.config['ALLOWED_THUMB_EXTENSIONS'])


def _get_storage_stats():
    upload_base = current_app.config['UPLOAD_FOLDER']
    total = 0
    for dirpath, _, filenames in os.walk(upload_base):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    # Stats from real DB
    total_photos    = Media.query.filter_by(media_type='photo', deleted_at=None).count()
    total_videos    = Media.query.filter_by(media_type='video', deleted_at=None).count()
    total_audio     = Media.query.filter_by(media_type='audio', deleted_at=None).count()
    published_media = Media.query.filter_by(status='published', deleted_at=None).count()
    draft_media     = Media.query.filter_by(status='draft', deleted_at=None).count()
    total_folders   = Folder.query.count()
    total_sessions  = ViewerSession.query.count()
    unique_names    = db.session.query(func.count(func.distinct(ViewerSession.normalized_name))).scalar()
    media_views     = db.session.query(func.sum(Media.view_count)).filter(Media.deleted_at == None).scalar() or 0
    storage_bytes   = _get_storage_stats()

    # Recent media
    recent_media = (Media.query.filter(Media.deleted_at == None)
                    .order_by(desc(Media.created_at)).limit(6).all())

    # Recent sessions
    recent_sessions = (ViewerSession.query.order_by(desc(ViewerSession.created_at)).limit(8).all())

    # Recent audit logs
    recent_logs = (AdminAuditLog.query.order_by(desc(AdminAuditLog.created_at)).limit(10).all())

    # Most viewed media
    top_media = (Media.query.filter(Media.deleted_at == None, Media.status == 'published')
                 .order_by(desc(Media.view_count)).limit(5).all())

    # Media type distribution for chart
    type_counts = {
        'Photos': total_photos,
        'Videos': total_videos,
        'Audio':  total_audio,
    }

    # Viewer activity last 14 days (for chart)
    today = utcnow().date()
    activity_labels = []
    activity_data   = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        cnt = (ViewerSession.query
               .filter(func.date(ViewerSession.created_at) == day)
               .count())
        activity_labels.append(day.strftime('%b %d'))
        activity_data.append(cnt)

    return render_template('admin/dashboard.html',
        total_photos=total_photos, total_videos=total_videos, total_audio=total_audio,
        published_media=published_media, draft_media=draft_media,
        total_folders=total_folders, total_sessions=total_sessions,
        unique_names=unique_names, media_views=media_views,
        storage_bytes=storage_bytes, storage_human=human_filesize(storage_bytes),
        recent_media=recent_media, recent_sessions=recent_sessions,
        recent_logs=recent_logs, top_media=top_media,
        type_counts=json.dumps(type_counts),
        activity_labels=json.dumps(activity_labels),
        activity_data=json.dumps(activity_data),
        format_duration=format_duration,
        human_filesize=human_filesize,
    )


# ---------------------------------------------------------------------------
# Media Library
# ---------------------------------------------------------------------------
@admin_bp.route('/media')
@admin_required
def media_library():
    page         = request.args.get('page', 1, type=int)
    per_page     = 20
    search       = request.args.get('q', '').strip()
    filter_type  = request.args.get('type', '')
    filter_status= request.args.get('status', '')
    filter_folder= request.args.get('folder_id', '', type=str)
    sort_by      = request.args.get('sort', 'newest')

    q = Media.query.filter(Media.deleted_at == None)

    if search:
        q = q.filter(or_(
            Media.title.ilike(f'%{search}%'),
            Media.description.ilike(f'%{search}%'),
            Media.tags.ilike(f'%{search}%'),
        ))
    if filter_type in ('photo', 'video', 'audio'):
        q = q.filter(Media.media_type == filter_type)
    if filter_status in ('published', 'draft'):
        q = q.filter(Media.status == filter_status)
    if filter_folder.isdigit():
        q = q.filter(Media.folder_id == int(filter_folder))
    elif filter_folder == 'none':
        q = q.filter(Media.folder_id == None)

    if sort_by == 'oldest':
        q = q.order_by(asc(Media.created_at))
    elif sort_by == 'title':
        q = q.order_by(asc(Media.title))
    elif sort_by == 'views':
        q = q.order_by(desc(Media.view_count))
    else:
        q = q.order_by(desc(Media.created_at))

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    folders = Folder.query.order_by(Folder.name).all()

    return render_template('admin/media.html',
        media=pagination.items, pagination=pagination,
        folders=folders, search=search,
        filter_type=filter_type, filter_status=filter_status,
        filter_folder=filter_folder, sort_by=sort_by,
        format_duration=format_duration, human_filesize=human_filesize,
    )


# ---------------------------------------------------------------------------
# Upload Media
# ---------------------------------------------------------------------------
@admin_bp.route('/upload', methods=['GET', 'POST'])
@admin_bp.route('/media/upload', methods=['GET', 'POST'])
@admin_required
def upload_media():
    folders = Folder.query.order_by(Folder.name).all()

    if request.method == 'POST':
        title      = request.form.get('title', '').strip()
        description= request.form.get('description', '').strip()
        caption    = request.form.get('caption', '').strip()
        tags       = request.form.get('tags', '').strip()
        media_type = request.form.get('media_type', '')
        status     = request.form.get('status', 'published')
        is_featured= request.form.get('is_featured') == '1'
        folder_id  = request.form.get('folder_id') or None
        artist     = request.form.get('artist', '').strip()
        file_obj   = request.files.get('media_file')
        thumb_obj  = request.files.get('thumbnail_file')

        errors = []
        if not title:
            errors.append('Title is required.')
        if media_type not in ('photo', 'video', 'audio'):
            errors.append('Please select a valid media type.')
        if not file_obj or not file_obj.filename:
            errors.append('Please select a file to upload.')

        allowed_map = {
            'photo': current_app.config['ALLOWED_IMAGE_EXTENSIONS'],
            'video': current_app.config['ALLOWED_VIDEO_EXTENSIONS'],
            'audio': current_app.config['ALLOWED_AUDIO_EXTENSIONS'],
        }
        if file_obj and file_obj.filename and media_type in allowed_map:
            if not allowed_file(file_obj.filename, allowed_map[media_type]):
                errors.append(f'File type not allowed for {media_type}.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('admin/upload.html', folders=folders)

        try:
            # Save main file
            stored_name, storage_path, file_size = save_upload(
                file_obj,
                subfolder=f'{media_type}s',
                allowed_exts=allowed_map[media_type],
            )
            mime_type = file_obj.content_type or ''

            # Save thumbnail
            thumbnail_path = None
            if thumb_obj and thumb_obj.filename:
                if allowed_file(thumb_obj.filename, current_app.config['ALLOWED_THUMB_EXTENSIONS']):
                    _, thumbnail_path, _ = save_upload(
                        thumb_obj,
                        subfolder='thumbnails',
                        allowed_exts=current_app.config['ALLOWED_THUMB_EXTENSIONS'],
                    )

            # Auto-generate thumbnail for photos
            if media_type == 'photo' and not thumbnail_path:
                upload_base = current_app.config['UPLOAD_FOLDER']
                source_full = os.path.join(upload_base, storage_path)
                thumb_fname = f'thumb_{stored_name.rsplit(".", 1)[0]}.jpg'
                thumbnail_path = generate_image_thumbnail(source_full, thumb_fname)

            media = Media(
                title           = title,
                description     = description,
                caption         = caption,
                tags            = tags,
                media_type      = media_type,
                stored_filename = stored_name,
                storage_path    = storage_path,
                thumbnail_path  = thumbnail_path,
                folder_id       = int(folder_id) if folder_id else None,
                status          = status,
                is_featured     = is_featured,
                mime_type       = mime_type,
                file_size       = file_size,
                artist          = artist if media_type == 'audio' else None,
                published_at    = utcnow() if status == 'published' else None,
            )
            db.session.add(media)
            db.session.commit()

            audit_log('admin_upload', 'media', media.id, f'type={media_type} title={title}')
            flash(f'"{title}" uploaded successfully.', 'success')
            return redirect(url_for('admin.edit_media', media_id=media.id))

        except Exception as exc:
            db.session.rollback()
            flash(f'Upload failed: {exc}', 'error')

    return render_template('admin/upload.html', folders=folders)


# ---------------------------------------------------------------------------
# Edit Media
# ---------------------------------------------------------------------------
@admin_bp.route('/media/<int:media_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_media(media_id):
    media   = Media.query.filter_by(id=media_id, deleted_at=None).first_or_404()
    folders = Folder.query.order_by(Folder.name).all()

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'delete':
            media.deleted_at = utcnow()
            media.status     = 'draft'
            db.session.commit()
            audit_log('admin_delete', 'media', media.id, media.title)
            flash(f'"{media.title}" moved to Recycle Bin.', 'success')
            return redirect(url_for('admin.media_library'))

        if action == 'replace_file':
            new_file = request.files.get('replace_file')
            if new_file and new_file.filename:
                allowed_map = {
                    'photo': current_app.config['ALLOWED_IMAGE_EXTENSIONS'],
                    'video': current_app.config['ALLOWED_VIDEO_EXTENSIONS'],
                    'audio': current_app.config['ALLOWED_AUDIO_EXTENSIONS'],
                }
                if allowed_file(new_file.filename, allowed_map.get(media.media_type, set())):
                    delete_file_safe(media.storage_path)
                    stored_name, storage_path, file_size = save_upload(
                        new_file, f'{media.media_type}s',
                        allowed_exts=allowed_map[media.media_type],
                    )
                    media.stored_filename = stored_name
                    media.storage_path    = storage_path
                    media.file_size       = file_size
                    media.mime_type       = new_file.content_type or ''
                    db.session.commit()
                    flash('File replaced successfully.', 'success')
                else:
                    flash('File type not allowed.', 'error')
            return redirect(url_for('admin.edit_media', media_id=media.id))

        # Regular save
        old_status       = media.status
        media.title      = request.form.get('title', '').strip() or media.title
        media.description= request.form.get('description', '').strip()
        media.caption    = request.form.get('caption', '').strip()
        media.tags       = request.form.get('tags', '').strip()
        media.artist     = request.form.get('artist', '').strip()
        media.is_featured= request.form.get('is_featured') == '1'
        folder_id        = request.form.get('folder_id') or None
        media.folder_id  = int(folder_id) if folder_id else None

        new_status = request.form.get('status', media.status)
        media.status = new_status
        if new_status == 'published' and old_status != 'published':
            media.published_at = utcnow()
            audit_log('admin_publish', 'media', media.id, media.title)
        elif new_status == 'draft' and old_status == 'published':
            audit_log('admin_unpublish', 'media', media.id, media.title)

        # New thumbnail
        thumb_obj = request.files.get('thumbnail_file')
        if thumb_obj and thumb_obj.filename:
            if allowed_file(thumb_obj.filename, current_app.config['ALLOWED_THUMB_EXTENSIONS']):
                delete_file_safe(media.thumbnail_path)
                _, thumbnail_path, _ = save_upload(
                    thumb_obj, 'thumbnails',
                    allowed_exts=current_app.config['ALLOWED_THUMB_EXTENSIONS'],
                )
                media.thumbnail_path = thumbnail_path

        media.updated_at = utcnow()
        db.session.commit()
        audit_log('admin_edit', 'media', media.id, media.title)
        flash('Changes saved.', 'success')

    return render_template('admin/edit_media.html',
        media=media, folders=folders,
        format_duration=format_duration,
        human_filesize=human_filesize,
    )



# ---------------------------------------------------------------------------
# Delete Media (Move to Recycle Bin)
# ---------------------------------------------------------------------------
@admin_bp.route('/media/<int:media_id>/delete', methods=['POST'])
@admin_required
def delete_media(media_id):
    media = Media.query.filter_by(id=media_id, deleted_at=None).first_or_404()
    media.deleted_at = utcnow()
    media.status     = 'draft'
    db.session.commit()
    audit_log('admin_delete', 'media', media.id, media.title)
    flash(f'"{media.title}" moved to Recycle Bin.', 'success')
    return redirect(request.referrer or url_for('admin.media_library'))


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------
@admin_bp.route('/media/bulk', methods=['POST'])
@admin_required
def media_bulk():
    ids    = request.form.getlist('selected_ids')
    action = request.form.get('bulk_action')

    if not ids:
        flash('No items selected.', 'warning')
        return redirect(url_for('admin.media_library'))

    media_list = Media.query.filter(Media.id.in_(ids), Media.deleted_at == None).all()

    if action == 'publish':
        for m in media_list:
            m.status       = 'published'
            m.published_at = utcnow()
        db.session.commit()
        flash(f'{len(media_list)} items published.', 'success')

    elif action == 'draft':
        for m in media_list:
            m.status = 'draft'
        db.session.commit()
        flash(f'{len(media_list)} items set to draft.', 'success')

    elif action == 'delete':
        for m in media_list:
            m.deleted_at = utcnow()
            m.status     = 'draft'
        db.session.commit()
        flash(f'{len(media_list)} items moved to Recycle Bin.', 'success')

    return redirect(url_for('admin.media_library'))


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
@admin_bp.route('/folders')
@admin_required
def folders():
    all_folders = (Folder.query.order_by(Folder.sort_order, Folder.name).all())
    return render_template('admin/folders.html', folders=all_folders)


@admin_bp.route('/folders/create', methods=['POST'])
@admin_required
def create_folder():
    name        = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    parent_id   = request.form.get('parent_id') or None
    visibility  = request.form.get('visibility', 'published')

    if not name:
        flash('Folder name is required.', 'error')
        return redirect(url_for('admin.folders'))

    folder = Folder(
        name              = name,
        description       = description,
        parent_id         = int(parent_id) if parent_id else None,
        visibility_status = visibility,
    )
    db.session.add(folder)
    db.session.commit()
    audit_log('create_folder', 'folder', folder.id, name)
    flash(f'Folder "{name}" created.', 'success')
    return redirect(url_for('admin.folders'))


@admin_bp.route('/folders/<int:folder_id>/edit', methods=['POST'])
@admin_required
def edit_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    folder.name              = request.form.get('name', '').strip() or folder.name
    folder.description       = request.form.get('description', '').strip()
    folder.visibility_status = request.form.get('visibility', folder.visibility_status)
    parent_id                = request.form.get('parent_id') or None
    if parent_id and int(parent_id) != folder.id:
        folder.parent_id = int(parent_id)
    else:
        folder.parent_id = None
    folder.updated_at = utcnow()
    db.session.commit()
    audit_log('edit_folder', 'folder', folder.id, folder.name)
    flash('Folder updated.', 'success')
    return redirect(url_for('admin.folders'))


@admin_bp.route('/folders/<int:folder_id>/delete', methods=['POST'])
@admin_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    action = request.form.get('action', 'trash_contents')

    if action == 'trash_contents':
        # Move all media in this folder to trash
        Media.query.filter_by(folder_id=folder_id, deleted_at=None).update(
            {'deleted_at': utcnow(), 'status': 'draft'}
        )
        db.session.commit()
    elif action == 'move_contents':
        target_id = request.form.get('target_folder_id')
        if target_id:
            Media.query.filter_by(folder_id=folder_id).update({'folder_id': int(target_id)})
            db.session.commit()
    # else: leave media without folder (unassigned)
    else:
        Media.query.filter_by(folder_id=folder_id).update({'folder_id': None})
        db.session.commit()

    # Move child folders to no parent
    Folder.query.filter_by(parent_id=folder_id).update({'parent_id': None})
    db.session.delete(folder)
    db.session.commit()
    audit_log('delete_folder', 'folder', folder_id, folder.name)
    flash(f'Folder "{folder.name}" deleted.', 'success')
    return redirect(url_for('admin.folders'))


# ---------------------------------------------------------------------------
# Viewers Activity
# ---------------------------------------------------------------------------
@admin_bp.route('/viewers')
@admin_required
def viewers():
    page        = request.args.get('page', 1, type=int)
    per_page    = 25
    search      = request.args.get('q', '').strip()
    filter_status = request.args.get('status', '')
    date_from   = request.args.get('date_from', '')
    date_to     = request.args.get('date_to', '')

    q = ViewerSession.query

    if search:
        q = q.filter(ViewerSession.display_name.ilike(f'%{search}%'))
    if filter_status in ('active', 'expired', 'ended'):
        q = q.filter(ViewerSession.session_status == filter_status)
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            q  = q.filter(ViewerSession.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            q  = q.filter(ViewerSession.created_at < dt)
        except ValueError:
            pass

    q = q.order_by(desc(ViewerSession.created_at))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    # Summary stats
    total_sessions  = ViewerSession.query.count()
    active_sessions = ViewerSession.query.filter_by(session_status='active').count()
    unique_names    = db.session.query(func.count(func.distinct(ViewerSession.normalized_name))).scalar()
    today_sessions  = ViewerSession.query.filter(
        func.date(ViewerSession.created_at) == utcnow().date()
    ).count()

    return render_template('admin/viewers.html',
        sessions=pagination.items, pagination=pagination,
        search=search, filter_status=filter_status,
        date_from=date_from, date_to=date_to,
        total_sessions=total_sessions, active_sessions=active_sessions,
        unique_names=unique_names, today_sessions=today_sessions,
    )


@admin_bp.route('/viewers/<int:session_id>/events')
@admin_required
def viewer_events(session_id):
    vs = ViewerSession.query.get_or_404(session_id)
    events = (MediaEvent.query
              .filter_by(viewer_session_id=session_id)
              .order_by(desc(MediaEvent.event_timestamp))
              .all())
    return render_template('admin/viewer_events.html', vs=vs, events=events)


@admin_bp.route('/viewers/export')
@admin_required
def export_viewers():
    import csv, io
    search      = request.args.get('q', '').strip()
    date_from   = request.args.get('date_from', '')
    date_to     = request.args.get('date_to', '')

    q = ViewerSession.query
    if search:
        q = q.filter(ViewerSession.display_name.ilike(f'%{search}%'))
    if date_from:
        try:
            q = q.filter(ViewerSession.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError: pass
    if date_to:
        try:
            q = q.filter(ViewerSession.created_at < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError: pass

    sessions = q.order_by(desc(ViewerSession.created_at)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Display Name', 'Normalized Name', 'Status', 'Login Date', 'Login Time',
                     'Last Activity', 'Ended At', 'Session Token (short)'])
    for s in sessions:
        writer.writerow([
            s.id, s.display_name, s.normalized_name, s.session_status,
            s.created_at.strftime('%Y-%m-%d') if s.created_at else '',
            s.created_at.strftime('%H:%M:%S') if s.created_at else '',
            s.last_activity_at.strftime('%Y-%m-%d %H:%M:%S') if s.last_activity_at else '',
            s.ended_at.strftime('%Y-%m-%d %H:%M:%S') if s.ended_at else '',
            s.session_token[:12] + '...',
        ])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=viewer_sessions.csv'},
    )


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
@admin_bp.route('/analytics')
@admin_required
def analytics():
    period   = request.args.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30

    date_from = utcnow() - timedelta(days=days)

    # Daily sessions for line chart
    daily_sessions = (db.session
        .query(func.date(ViewerSession.created_at).label('day'),
               func.count().label('cnt'))
        .filter(ViewerSession.created_at >= date_from)
        .group_by(func.date(ViewerSession.created_at))
        .order_by('day')
        .all())

    labels = [str(r.day) for r in daily_sessions]
    data   = [r.cnt for r in daily_sessions]

    # Most viewed media
    top_photos = (Media.query.filter_by(media_type='photo', deleted_at=None)
                  .order_by(desc(Media.view_count)).limit(10).all())
    top_videos = (Media.query.filter_by(media_type='video', deleted_at=None)
                  .order_by(desc(Media.view_count)).limit(10).all())
    top_audio  = (Media.query.filter_by(media_type='audio', deleted_at=None)
                  .order_by(desc(Media.view_count)).limit(10).all())

    # Upload trend (last 30 days)
    upload_trend = (db.session
        .query(func.date(Media.created_at).label('day'), func.count().label('cnt'))
        .filter(Media.created_at >= date_from, Media.deleted_at == None)
        .group_by(func.date(Media.created_at))
        .order_by('day')
        .all())
    upload_labels = [str(r.day) for r in upload_trend]
    upload_data   = [r.cnt for r in upload_trend]

    # Most viewed folders
    folder_views = (db.session
        .query(Folder.name,
               func.count(MediaEvent.id).label('views'))
        .join(MediaEvent, MediaEvent.folder_id == Folder.id)
        .filter(MediaEvent.event_type == 'folder_open')
        .group_by(Folder.id, Folder.name)
        .order_by(desc('views'))
        .limit(8).all())

    # Unique names by day
    unique_by_day = (db.session
        .query(func.date(ViewerSession.created_at).label('day'),
               func.count(func.distinct(ViewerSession.normalized_name)).label('cnt'))
        .filter(ViewerSession.created_at >= date_from)
        .group_by(func.date(ViewerSession.created_at))
        .order_by('day')
        .all())

    # Totals
    total_sessions    = ViewerSession.query.count()
    unique_names      = db.session.query(func.count(func.distinct(ViewerSession.normalized_name))).scalar()
    total_media_views = db.session.query(func.sum(Media.view_count)).filter(Media.deleted_at == None).scalar() or 0
    total_likes       = MediaLike.query.count()
    total_favs        = MediaFavourite.query.count()
    storage_bytes     = _get_storage_stats()

    return render_template('admin/analytics.html',
        period=period,
        daily_labels=json.dumps(labels),
        daily_data=json.dumps(data),
        upload_labels=json.dumps(upload_labels),
        upload_data=json.dumps(upload_data),
        folder_views=folder_views,
        top_photos=top_photos, top_videos=top_videos, top_audio=top_audio,
        unique_by_day=unique_by_day,
        total_sessions=total_sessions, unique_names=unique_names,
        total_media_views=total_media_views, total_likes=total_likes,
        total_favs=total_favs,
        storage_bytes=storage_bytes, storage_human=human_filesize(storage_bytes),
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        bool_keys = ['allow_likes', 'allow_favourites', 'allow_downloads',
                     'allow_comments', 'allow_share_links', 'show_view_counts']
        text_keys = ['gallery_title', 'gallery_subtitle', 'items_per_page']

        for key in bool_keys:
            val = '1' if request.form.get(key) else '0'
            s = AppSetting.query.get(key)
            if s:
                s.value = val
            else:
                db.session.add(AppSetting(key=key, value=val))

        for key in text_keys:
            val = request.form.get(key, '').strip()
            if val:
                s = AppSetting.query.get(key)
                if s:
                    s.value = val
                else:
                    db.session.add(AppSetting(key=key, value=val))

        db.session.commit()
        audit_log('update_settings', 'setting')
        flash('Settings saved.', 'success')
        return redirect(url_for('admin.settings'))

    cfg = get_settings_dict()
    return render_template('admin/settings.html', cfg=cfg)


# ---------------------------------------------------------------------------
# Recycle Bin
# ---------------------------------------------------------------------------
@admin_bp.route('/trash')
@admin_required
def trash():
    page       = request.args.get('page', 1, type=int)
    deleted_q  = (Media.query.filter(Media.deleted_at != None)
                  .order_by(desc(Media.deleted_at)))
    pagination = deleted_q.paginate(page=page, per_page=25, error_out=False)
    return render_template('admin/trash.html',
        media=pagination.items, pagination=pagination,
        format_duration=format_duration, human_filesize=human_filesize,
    )


@admin_bp.route('/trash/<int:media_id>/restore', methods=['POST'])
@admin_required
def restore_media(media_id):
    media = Media.query.filter(Media.id == media_id, Media.deleted_at != None).first_or_404()
    media.deleted_at = None
    media.status     = 'draft'
    db.session.commit()
    audit_log('admin_restore', 'media', media.id, media.title)
    flash(f'"{media.title}" restored to draft.', 'success')
    return redirect(url_for('admin.trash'))


@admin_bp.route('/trash/<int:media_id>/destroy', methods=['POST'])
@admin_required
def destroy_media(media_id):
    media = Media.query.filter(Media.id == media_id, Media.deleted_at != None).first_or_404()
    # Delete files
    delete_file_safe(media.storage_path)
    delete_file_safe(media.thumbnail_path)
    title = media.title
    db.session.delete(media)
    db.session.commit()
    audit_log('admin_destroy', 'media', media_id, title)
    flash(f'"{title}" permanently deleted.', 'success')
    return redirect(url_for('admin.trash'))


@admin_bp.route('/trash/empty', methods=['POST'])
@admin_required
def empty_trash():
    deleted_media = Media.query.filter(Media.deleted_at != None).all()
    for m in deleted_media:
        delete_file_safe(m.storage_path)
        delete_file_safe(m.thumbnail_path)
        db.session.delete(m)
    db.session.commit()
    audit_log('empty_trash', 'media', details=f'{len(deleted_media)} items permanently deleted')
    flash(f'Trash emptied. {len(deleted_media)} items permanently deleted.', 'success')
    return redirect(url_for('admin.trash'))
