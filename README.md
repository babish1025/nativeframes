# NATIVEFRAMES — Premium Private Mini Gallery Platform

> **"Every frame tells a story."**

A complete, production-grade mini gallery web platform engineered with a dark cinematic aesthetic, warm champagne-gold accents, robust security safeguards, and comprehensive viewer telemetry tracking.

---

## 🌟 Key Features

### 1. Brand Identity & Cinematic Aesthetic
- **Official Brand Mark**: Official high-contrast NATIVEFRAMES insignia utilized consistently across navigation topbars, viewer entry cards, and the admin studio.
- **Color Architecture**: Deep matte black canvas (`#080808` / `#121215`), subtle surface elevation cards, and curated champagne-gold accents (`#D4AF37`).
- **Interactive Lightbox & Media Showcase**: Instant full-viewport photograph viewer with keyboard navigation (`Esc`, `←`, `→`), dedicated video theater player with progress monitoring, and a persistent sticky audio mini-player with waveform seeker.

### 2. Private Viewer Experience
- **Name-Only Entry Gate (`/auth/viewer`)**: Zero friction access requiring only the guest's name; issues a secure 64-character session token.
- **Granular Interaction Tracking**: Automatically audits session start/end, folder views, photo zooms, video watch milestones (25%, 50%, 75%, 100%), and audio playback starts.
- **Audience Engagement**: Real-time AJAX Heart Reactions (Likes) and personal Favourites bookmarks (`★`).

### 3. Professional Admin Studio (`/admin/dashboard`)
- **Executive Telemetry Dashboard**: Real-time KPI statistics (Total frames, impressions, storage consumed, viewer sessions) and interactive Chart.js graphs.
- **Media Asset Library (`/admin/media`)**: Comprehensive filter, search, and sorting controls for photography, video clips, and audio tracks.
- **Media Upload Hub (`/admin/upload`)**: Drag-and-drop dropzone, auto-thumbnail generation via Pillow, custom poster support, and instant publishing controls.
- **Folder & Album Manager (`/admin/folders`)**: Create and organize nested album hierarchies with safe deletion modes (move to trash vs unassign).
- **Viewer Intelligence & Audit Timeline (`/admin/viewers`)**: Inspect IP addresses, user agents, active sessions, granular event streams, and one-click CSV export.
- **Recycle Bin & Safe Purging (`/admin/trash`)**: Soft-delete safety net with single-click restore or permanent storage disk purging.
- **Platform Settings (`/admin/settings`)**: Live toggles for heart reactions, favourites, direct master downloads, view counter visibility, and gallery branding.

### 4. Security & Production Engineering
- **CSRF Protection**: All form submissions and AJAX mutation endpoints enforce cryptographic Flask-WTF tokens.
- **Brute-Force Rate Limiting**: Exponential lockout on consecutive failed admin login attempts.
- **Protected File Serving**: Media assets in `/uploads/` are strictly served to authorized admin sessions or active viewer sessions.
- **Database Engine**: Production MySQL 8.0 support (Railway compatible) with graceful local offline SQLite fallback for rapid testing.

---

## 🚀 Quick Start Guide

### 1. Environment & Dependencies
```bash
# Install required dependencies
pip install -r requirements.txt
```

### 2. Configuration (`.env`)
The application comes preconfigured with default credentials in `.env`:
```ini
SECRET_KEY=nf-super-secret-key-2024-change-in-production
DATABASE_URL=mysql+pymysql://root:password@mysql.railway.internal:3306/railway
ADMIN_USERNAME=nativeframes
ADMIN_PASSWORD=NativeFrames@2024
UPLOAD_FOLDER=uploads
MAX_UPLOAD_MB=500
```
> *Note: When running locally outside of Railway, the application automatically detects that `mysql.railway.internal` is an internal container hostname and seamlessly operates using a local SQLite database (`nativeframes.db`).*

### 3. Launching the Application
```bash
python run.py
```
Visit the running application in your browser:
- **Welcome / Landing Page**: [http://localhost:5000/](http://localhost:5000/)
- **Viewer Entry Gate**: [http://localhost:5000/auth/viewer](http://localhost:5000/auth/viewer)
- **Admin Studio Login**: [http://localhost:5000/auth/admin/login](http://localhost:5000/auth/admin/login)

---

## 🔑 Default Admin Credentials
- **Username**: `nativeframes`
- **Password**: `NativeFrames@2024`

---

## 📁 Project Architecture
```
NativeFrames new/
├── run.py                       # Application execution entry point
├── requirements.txt             # Python package dependencies
├── .env                         # Environment variables & secrets
├── .env.example                 # Example configuration template
├── migrations/
│   ├── schema.sql               # Universal database DDL schema
│   └── schema_mysql.sql         # Production MySQL 8.0+ schema
├── uploads/                     # Master uploaded media storage
│   ├── photos/
│   ├── videos/
│   ├── audio/
│   └── thumbnails/
└── app/
    ├── __init__.py              # Flask app factory & upload routing
    ├── config.py                # Environment-aware configuration
    ├── models.py                # SQLAlchemy models & relationships
    ├── utils.py                 # Security decorators, rate limiting & helpers
    ├── admin/                   # Admin Studio Blueprint routes
    ├── auth/                    # Viewer & Admin authentication Blueprint routes
    ├── gallery/                 # Public Gallery viewer Blueprint routes
    ├── api/                     # AJAX interaction & telemetry Blueprint routes
    ├── static/
    │   ├── css/main.css         # Complete design system & tokens
    │   ├── js/main.js           # Lightbox, audio player, AJAX handlers
    │   └── images/              # Official brand logos & favicons
    └── templates/               # Jinja2 HTML templates
        ├── base_admin.html
        ├── base_gallery.html
        ├── index.html
        ├── admin/
        ├── auth/
        ├── errors/
        └── gallery/
```
