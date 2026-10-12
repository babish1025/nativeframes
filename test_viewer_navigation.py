"""
NativeFrames — Comprehensive Viewer Navigation & Folder Filtering Test
Tests all requirements from section 7 of the user prompt:
1. Create Folder A and Folder B.
2. Upload a video into Folder A and another video into Folder B.
3. Log in as a viewer.
4. Confirm the home page displays folders rather than every video.
5. Open Folder A and verify that only its video appears.
6. Open Folder B and verify that only its video appears.
7. Test the Photos, Videos, Audio and All filters.
8. Test subfolder navigation and breadcrumbs.
9. Navigate away and return; verify folder contents remain correct.
10. Refresh the page and verify the selected folder's contents are still correct.
11. Confirm empty folders show the correct empty state ("This folder is empty.").
12. Confirm unpublished media is not visible to viewers.
"""
import sys
from app import create_app
from app.models import db, Folder, Media, ViewerSession
from app.utils import utcnow

def run_tests():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    client = app.test_client()

    print("=" * 70)
    print("STARTING NATIVEFRAMES VIEWER NAVIGATION TESTS")
    print("=" * 70)

    with app.app_context():
        # Setup: Ensure clean state for test folders and media
        # Clean up existing test records if any
        test_folder_names = ["Test Folder A", "Test Folder B", "Subfolder A1", "Empty Test Folder"]
        for f in Folder.query.filter(Folder.name.in_(test_folder_names)).all():
            Media.query.filter_by(folder_id=f.id).delete()
            db.session.delete(f)
        db.session.commit()

        # Step 1: Create Folder A and Folder B
        folder_a = Folder(name="Test Folder A", description="Collection A description", visibility_status="published", sort_order=1)
        folder_b = Folder(name="Test Folder B", description="Collection B description", visibility_status="published", sort_order=2)
        folder_empty = Folder(name="Empty Test Folder", description="Empty folder description", visibility_status="published", sort_order=3)
        db.session.add_all([folder_a, folder_b, folder_empty])
        db.session.commit()

        # Subfolder inside Folder A
        subfolder_a1 = Folder(name="Subfolder A1", parent_id=folder_a.id, visibility_status="published", sort_order=1)
        db.session.add(subfolder_a1)
        db.session.commit()

        # Step 2: Upload/assign media
        # Video in Folder A
        vid_a = Media(
            title="Video Alpha In Folder A",
            media_type="video",
            folder_id=folder_a.id,
            status="published",
            storage_path="videos/vid_a.mp4",
            published_at=utcnow()
        )
        # Photo in Folder A
        photo_a = Media(
            title="Photo Alpha In Folder A",
            media_type="photo",
            folder_id=folder_a.id,
            status="published",
            storage_path="photos/photo_a.jpg",
            published_at=utcnow()
        )
        # Audio in Folder A
        audio_a = Media(
            title="Audio Alpha In Folder A",
            media_type="audio",
            folder_id=folder_a.id,
            status="published",
            storage_path="audio/audio_a.mp3",
            published_at=utcnow()
        )
        # Video in Folder B
        vid_b = Media(
            title="Video Beta In Folder B",
            media_type="video",
            folder_id=folder_b.id,
            status="published",
            storage_path="videos/vid_b.mp4",
            published_at=utcnow()
        )
        # Photo in Subfolder A1
        photo_sub = Media(
            title="Photo In Subfolder A1",
            media_type="photo",
            folder_id=subfolder_a1.id,
            status="published",
            storage_path="photos/photo_sub.jpg",
            published_at=utcnow()
        )
        # Unpublished media in Folder A (draft)
        draft_media = Media(
            title="Secret Draft Media",
            media_type="photo",
            folder_id=folder_a.id,
            status="draft",
            storage_path="photos/draft.jpg",
            published_at=None
        )

        db.session.add_all([vid_a, photo_a, audio_a, vid_b, photo_sub, draft_media])
        db.session.commit()

        fa_id = folder_a.id
        fb_id = folder_b.id
        fempty_id = folder_empty.id
        fsub_id = subfolder_a1.id

    # Step 3: Log in as a viewer
    resp = client.post('/auth/viewer', data={'name': 'Test Viewer Alice'}, follow_redirects=True)
    assert resp.status_code == 200, f"Viewer login failed with status {resp.status_code}"
    print("[PASS] Step 3: Viewer logged in successfully.")

    # Step 4: Confirm Home Page displays folders rather than every video
    resp = client.get('/gallery/')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Folders should appear on home page
    assert "Test Folder A" in html, "Test Folder A not found on Viewer Home Page"
    assert "Test Folder B" in html, "Test Folder B not found on Viewer Home Page"
    # Specific media titles MUST NOT appear on Viewer Home Page by default
    assert "Video Alpha In Folder A" not in html, "FAIL: Video Alpha In Folder A should NOT appear on Home Page!"
    assert "Video Beta In Folder B" not in html, "FAIL: Video Beta In Folder B should NOT appear on Home Page!"
    assert "Photo Alpha In Folder A" not in html, "FAIL: Photo Alpha In Folder A should NOT appear on Home Page!"
    print("[PASS] Step 4: Viewer Home Page displays folders and does NOT dump media by default.")

    # Step 5: Open Folder A and verify only its media appears
    resp = client.get(f'/gallery/folder/{fa_id}')
    assert resp.status_code == 200
    html_a = resp.get_data(as_text=True)

    assert "Test Folder A" in html_a
    assert "Video Alpha In Folder A" in html_a, "Video Alpha In Folder A should appear in Folder A"
    assert "Photo Alpha In Folder A" in html_a, "Photo Alpha In Folder A should appear in Folder A"
    assert "Audio Alpha In Folder A" in html_a, "Audio Alpha In Folder A should appear in Folder A"
    assert "Video Beta In Folder B" not in html_a, "FAIL: Video Beta In Folder B should NOT appear in Folder A!"
    assert "Photo In Subfolder A1" not in html_a, "FAIL: Subfolder media should not appear directly in parent folder media grid!"
    print("[PASS] Step 5: Open Folder A — only Folder A's direct media appears.")

    # Step 6: Open Folder B and verify only its video appears
    resp = client.get(f'/gallery/folder/{fb_id}')
    assert resp.status_code == 200
    html_b = resp.get_data(as_text=True)

    assert "Test Folder B" in html_b
    assert "Video Beta In Folder B" in html_b, "Video Beta In Folder B should appear in Folder B"
    assert "Video Alpha In Folder A" not in html_b, "FAIL: Video Alpha In Folder A should NOT appear in Folder B!"
    assert "Photo Alpha In Folder A" not in html_b, "FAIL: Photo Alpha In Folder A should NOT appear in Folder B!"
    print("[PASS] Step 6: Open Folder B — only Folder B's media appears.")

    # Step 7: Test category filters (Photos, Videos, Audio, All) in Folder A
    # Filter Videos
    resp_vid = client.get(f'/gallery/folder/{fa_id}?type=videos')
    html_vid = resp_vid.get_data(as_text=True)
    assert "Video Alpha In Folder A" in html_vid, "Video Alpha should appear under Videos filter"
    assert "Photo Alpha In Folder A" not in html_vid, "Photo Alpha should NOT appear under Videos filter"
    assert "Audio Alpha In Folder A" not in html_vid, "Audio Alpha should NOT appear under Videos filter"
    assert "Video Beta In Folder B" not in html_vid, "Video Beta should NOT appear (scoped to Folder A)"

    # Filter Photos
    resp_photo = client.get(f'/gallery/folder/{fa_id}?type=photos')
    html_photo = resp_photo.get_data(as_text=True)
    assert "Photo Alpha In Folder A" in html_photo, "Photo Alpha should appear under Photos filter"
    assert "Video Alpha In Folder A" not in html_photo, "Video Alpha should NOT appear under Photos filter"
    assert "Audio Alpha In Folder A" not in html_photo, "Audio Alpha should NOT appear under Photos filter"

    # Filter Audio
    resp_audio = client.get(f'/gallery/folder/{fa_id}?type=audio')
    html_audio = resp_audio.get_data(as_text=True)
    assert "Audio Alpha In Folder A" in html_audio, "Audio Alpha should appear under Audio filter"
    assert "Photo Alpha In Folder A" not in html_audio, "Photo Alpha should NOT appear under Audio filter"
    assert "Video Alpha In Folder A" not in html_audio, "Video Alpha should NOT appear under Audio filter"

    # Filter All
    resp_all = client.get(f'/gallery/folder/{fa_id}?type=all')
    html_all = resp_all.get_data(as_text=True)
    assert "Video Alpha In Folder A" in html_all
    assert "Photo Alpha In Folder A" in html_all
    assert "Audio Alpha In Folder A" in html_all
    print("[PASS] Step 7: Photos, Videos, Audio, and All category filters work perfectly inside folder.")

    # Step 8: Test Subfolder navigation & Breadcrumbs
    # In Folder A, subfolder A1 should be displayed first
    assert "Subfolder A1" in html_a, "Subfolder A1 should be displayed in Folder A"
    assert "Subfolders" in html_a or "subfolder" in html_a.lower()

    # Open Subfolder A1
    resp_sub = client.get(f'/gallery/folder/{fsub_id}')
    assert resp_sub.status_code == 200
    html_sub = resp_sub.get_data(as_text=True)

    assert "Subfolder A1" in html_sub
    assert "Photo In Subfolder A1" in html_sub, "Photo In Subfolder A1 should appear in Subfolder A1"
    assert "Video Alpha In Folder A" not in html_sub, "Parent folder media should NOT appear in subfolder!"

    # Check breadcrumbs: Home > Test Folder A > Subfolder A1
    assert "Home" in html_sub
    assert "Test Folder A" in html_sub
    assert "Subfolder A1" in html_sub
    assert f"/gallery/folder/{fa_id}" in html_sub, "Breadcrumbs should link back to parent Test Folder A"

    # Breadcrumbs with filter e.g. Videos
    resp_sub_vid = client.get(f'/gallery/folder/{fsub_id}?type=videos')
    html_sub_vid = resp_sub_vid.get_data(as_text=True)
    assert "Videos" in html_sub_vid, "Breadcrumb should include active filter label 'Videos'"
    print("[PASS] Step 8: Subfolder navigation and breadcrumbs (Home > Folder A > Subfolder A1) work correctly.")

    # Step 9: Navigate away and return; verify folder contents remain correct
    client.get('/gallery/')
    resp_return = client.get(f'/gallery/folder/{fa_id}')
    assert "Video Alpha In Folder A" in resp_return.get_data(as_text=True)
    print("[PASS] Step 9: Navigate away and return — folder contents remain correct.")

    # Step 10: Refresh the page (re-GET); verify contents remain correct
    resp_refresh = client.get(f'/gallery/folder/{fa_id}')
    assert "Video Alpha In Folder A" in resp_refresh.get_data(as_text=True)
    print("[PASS] Step 10: Refresh folder page — contents still correct.")

    # Step 11: Confirm empty folders show the correct empty state ("This folder is empty.")
    resp_empty = client.get(f'/gallery/folder/{fempty_id}')
    assert resp_empty.status_code == 200
    html_empty = resp_empty.get_data(as_text=True)
    assert "This folder is empty." in html_empty, f"Expected 'This folder is empty.' in empty folder view. Got: {html_empty}"
    print("[PASS] Step 11: Empty folder displays 'This folder is empty.'")

    # Step 12: Confirm unpublished media is not visible to viewers
    assert "Secret Draft Media" not in html_a, "FAIL: Unpublished draft media was visible to viewer in Folder A!"
    assert "Secret Draft Media" not in html, "FAIL: Unpublished draft media was visible to viewer on Home Page!"
    print("[PASS] Step 12: Unpublished media is strictly hidden from viewers.")

    # Bonus Step: Test JSON API endpoints
    resp_api_folders = client.get('/api/gallery/folders')
    assert resp_api_folders.status_code == 200
    data_f = resp_api_folders.get_json()
    assert data_f['success'] is True
    folder_names = [f['name'] for f in data_f['folders']]
    assert "Test Folder A" in folder_names
    assert "Test Folder B" in folder_names

    resp_api_media = client.get(f'/api/gallery/media?folder_id={fa_id}&type=videos')
    assert resp_api_media.status_code == 200
    data_m = resp_api_media.get_json()
    assert data_m['success'] is True
    titles = [m['title'] for m in data_m['media']]
    assert "Video Alpha In Folder A" in titles
    assert "Video Beta In Folder B" not in titles
    print("[PASS] Bonus: /api/gallery/folders and /api/gallery/media JSON endpoints verified.")

    print("=" * 70)
    print("ALL 12 TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
