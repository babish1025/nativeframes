/**
 * NativeFrames — Main JavaScript
 * Gallery interactions, lightbox, audio player, uploads, AJAX
 */

/* ============================================================
   CSRF Token helper (Flask-WTF)
   ============================================================ */
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

async function apiPost(url, body = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(body),
  });
  return res.json();
}

/* ============================================================
   Toast Notifications
   ============================================================ */
const ToastManager = {
  container: null,
  init() {
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    document.body.appendChild(this.container);
  },
  show(message, type = 'info', duration = 4000) {
    if (!this.container) this.init();
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    this.container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all .3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },
};
ToastManager.init();

/* ============================================================
   Sidebar Toggle
   ============================================================ */
function initSidebar() {
  const toggle  = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.nf-sidebar');
  const main    = document.querySelector('.admin-main');
  if (!toggle || !sidebar) return;

  const isMobile = () => window.innerWidth <= 768;

  toggle.addEventListener('click', () => {
    if (isMobile()) {
      sidebar.classList.toggle('mobile-open');
      // Overlay
      let overlay = document.getElementById('sidebar-overlay');
      if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'sidebar-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:99;display:none;';
        overlay.addEventListener('click', () => {
          sidebar.classList.remove('mobile-open');
          overlay.style.display = 'none';
        });
        document.body.appendChild(overlay);
      }
      overlay.style.display = sidebar.classList.contains('mobile-open') ? 'block' : 'none';
    } else {
      sidebar.classList.toggle('collapsed');
      main?.classList.toggle('sidebar-collapsed');
    }
  });
}

/* ============================================================
   Lightbox (Image viewer)
   ============================================================ */
const Lightbox = {
  overlay: null,
  img: null,
  closeBtn: null,
  prevBtn: null,
  nextBtn: null,
  captionEl: null,
  items: [],   // Array of {src, title, caption}
  current: 0,

  init() {
    this.overlay = document.createElement('div');
    this.overlay.className = 'lightbox-overlay';
    this.overlay.innerHTML = `
      <div class="lightbox-content">
        <div class="lightbox-spinner" id="lb-spinner" style="display:none; width:44px; height:44px; border:3px solid rgba(212,175,55,0.2); border-top-color:var(--nf-gold); border-radius:50%; animation:spin 0.8s linear infinite;"></div>
        <img class="lightbox-img" src="" alt="" style="max-width:90vw; max-height:85vh; object-fit:contain; border-radius:8px; box-shadow:0 12px 40px rgba(0,0,0,0.8);" />
      </div>
      <button class="lightbox-close" aria-label="Close">✕</button>
      <button class="lightbox-nav prev" aria-label="Previous">‹</button>
      <button class="lightbox-nav next" aria-label="Next">›</button>
      <div class="lightbox-caption">
        <h4 class="lb-title"></h4>
        <p class="lb-sub"></p>
      </div>`;
    document.body.appendChild(this.overlay);

    this.img       = this.overlay.querySelector('.lightbox-img');
    this.spinner   = this.overlay.querySelector('#lb-spinner');
    this.closeBtn  = this.overlay.querySelector('.lightbox-close');
    this.prevBtn   = this.overlay.querySelector('.prev');
    this.nextBtn   = this.overlay.querySelector('.next');
    this.captionEl = this.overlay.querySelector('.lightbox-caption');

    this.closeBtn.addEventListener('click', () => this.close());
    this.prevBtn.addEventListener('click',  () => this.navigate(-1));
    this.nextBtn.addEventListener('click',  () => this.navigate(1));
    this.overlay.addEventListener('click', e => {
      if (e.target === this.overlay) this.close();
    });
    document.addEventListener('keydown', e => {
      if (!this.overlay.classList.contains('open')) return;
      if (e.key === 'Escape')      this.close();
      if (e.key === 'ArrowLeft')   this.navigate(-1);
      if (e.key === 'ArrowRight')  this.navigate(1);
    });

    // Mobile touch swipe gestures
    let touchStartX = 0;
    let touchStartY = 0;
    this.overlay.addEventListener('touchstart', e => {
      if (e.touches && e.touches.length === 1) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
      }
    }, { passive: true });
    this.overlay.addEventListener('touchend', e => {
      if (e.changedTouches && e.changedTouches.length === 1) {
        const diffX = e.changedTouches[0].clientX - touchStartX;
        const diffY = e.changedTouches[0].clientY - touchStartY;
        if (Math.abs(diffX) > 40 && Math.abs(diffX) > Math.abs(diffY)) {
          if (diffX < 0) this.navigate(1);
          else this.navigate(-1);
        }
      }
    }, { passive: true });
  },

  open(items, index = 0) {
    this.items   = items;
    this.current = index;
    this._show();
    this.overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  },

  close() {
    this.overlay.classList.remove('open');
    document.body.style.overflow = '';
    this.img.src = '';
  },

  navigate(dir) {
    this.current = (this.current + dir + this.items.length) % this.items.length;
    this._show();
  },

  _show() {
    const item = this.items[this.current];
    if (!item) return;
    if (this.spinner) this.spinner.style.display = 'block';
    this.img.style.opacity = '0';
    this.img.onload = () => {
      if (this.spinner) this.spinner.style.display = 'none';
      this.img.style.opacity = '1';
      this.img.style.transition = 'opacity 0.25s ease';
    };
    this.img.onerror = () => {
      if (this.spinner) this.spinner.style.display = 'none';
      this.img.style.opacity = '1';
    };
    this.img.src = item.src;
    this.overlay.querySelector('.lb-title').textContent = item.title || '';
    this.overlay.querySelector('.lb-sub').textContent   = item.caption || '';
    this.prevBtn.style.display = this.items.length > 1 ? 'flex' : 'none';
    this.nextBtn.style.display = this.items.length > 1 ? 'flex' : 'none';
    // Log event
    if (item.mediaId) {
      apiPost('/api/event', { event_type: 'image_open', media_id: item.mediaId });
    }
  },
};
Lightbox.init();

/* ============================================================
   Gallery Media Cards — click handlers
   ============================================================ */
function initGalleryCards() {
  const photoItems = [];
  let photoIdx = 0;

  document.querySelectorAll('.media-card[data-type="photo"]').forEach((card, i) => {
    const src     = card.dataset.src;
    const title   = card.dataset.title   || '';
    const caption = card.dataset.caption || '';
    const mediaId = card.dataset.mediaId;
    photoItems.push({ src, title, caption, mediaId });

    card.addEventListener('click', () => {
      Lightbox.open(photoItems, i);
    });
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        Lightbox.open(photoItems, i);
      }
    });
  });

  // Video cards — open inline player
  document.querySelectorAll('.media-card[data-type="video"]').forEach(card => {
    card.addEventListener('click', () => {
      const href = card.dataset.href;
      if (href) window.location.href = href;
    });
  });

  // Audio cards
  document.querySelectorAll('.media-card[data-type="audio"]').forEach(card => {
    card.addEventListener('click', () => {
      const src     = card.dataset.src;
      const title   = card.dataset.title  || '';
      const artist  = card.dataset.artist || '';
      const thumb   = card.dataset.thumb  || '';
      const mediaId = card.dataset.mediaId;
      if (src) AudioPlayer.play({ src, title, artist, thumb, mediaId });
    });
  });
}

/* ============================================================
   Like / Favourite AJAX
   ============================================================ */
function initInteractions() {
  document.querySelectorAll('[data-action="like"]').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      const mediaId = btn.dataset.mediaId;
      try {
        const data = await apiPost(`/api/like/${mediaId}`);
        btn.classList.toggle('active', data.liked);
        const count = btn.querySelector('.like-count');
        if (count && data.count !== undefined) count.textContent = data.count;
        ToastManager.show(data.liked ? 'Liked!' : 'Like removed', 'success', 2000);
      } catch (err) {
        ToastManager.show('Could not update like.', 'error');
      }
    });
  });

  document.querySelectorAll('[data-action="favourite"]').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      const mediaId = btn.dataset.mediaId;
      try {
        const data = await apiPost(`/api/favourite/${mediaId}`);
        btn.classList.toggle('active', data.favourited);
        ToastManager.show(data.favourited ? 'Added to favourites' : 'Removed from favourites', 'success', 2000);
      } catch (err) {
        ToastManager.show('Could not update favourite.', 'error');
      }
    });
  });
}

/* ============================================================
   Mini Audio Player
   ============================================================ */
const AudioPlayer = {
  bar: null,
  audio: null,
  playPauseBtn: null,
  seekEl: null,
  currentTimeEl: null,
  durationEl: null,
  titleEl: null,
  artistEl: null,
  thumbEl: null,
  mediaId: null,
  eventSent: { start: false, progress25: false, progress50: false, progress75: false, complete: false },

  init() {
    this.bar = document.getElementById('mini-player');
    if (!this.bar) return;

    this.audio          = document.getElementById('mini-audio');
    this.playPauseBtn   = this.bar.querySelector('.play-pause');
    this.seekEl         = this.bar.querySelector('.player-seek');
    this.currentTimeEl  = this.bar.querySelector('.current-time');
    this.durationEl     = this.bar.querySelector('.total-time');
    this.titleEl        = this.bar.querySelector('.mini-player-title');
    this.artistEl       = this.bar.querySelector('.mini-player-artist');
    this.thumbEl        = this.bar.querySelector('.mini-player-thumb');

    if (!this.audio) return;

    this.playPauseBtn?.addEventListener('click', () => this.togglePlay());

    this.audio.addEventListener('timeupdate', () => {
      const { currentTime, duration } = this.audio;
      if (this.currentTimeEl) this.currentTimeEl.textContent = this._fmt(currentTime);
      if (this.seekEl && duration) this.seekEl.value = (currentTime / duration) * 100;
      this._checkProgress(currentTime, duration);
    });

    this.audio.addEventListener('loadedmetadata', () => {
      if (this.durationEl) this.durationEl.textContent = this._fmt(this.audio.duration);
    });

    this.audio.addEventListener('ended', () => {
      this.playPauseBtn.textContent = '▶';
      if (!this.eventSent.complete && this.mediaId) {
        apiPost('/api/event', { event_type: 'audio_complete', media_id: this.mediaId });
        this.eventSent.complete = true;
      }
    });

    this.seekEl?.addEventListener('input', () => {
      const pct = this.seekEl.value / 100;
      this.audio.currentTime = pct * this.audio.duration;
    });

    const closeBtn = this.bar.querySelector('.mini-player-close');
    closeBtn?.addEventListener('click', () => {
      this.audio.pause();
      this.bar.classList.remove('visible');
    });
  },

  play({ src, title, artist, thumb, mediaId }) {
    if (!this.bar || !this.audio) return;
    this.mediaId = mediaId;
    this.eventSent = { start: false, progress25: false, progress50: false, progress75: false, complete: false };
    this.audio.src = src;
    this.audio.play();
    if (this.titleEl)  this.titleEl.textContent  = title  || 'Unknown';
    if (this.artistEl) this.artistEl.textContent = artist || '';
    if (this.thumbEl)  {
      this.thumbEl.src   = thumb || '';
      this.thumbEl.style.display = thumb ? 'block' : 'none';
    }
    this.playPauseBtn.textContent = '⏸';
    this.bar.classList.add('visible');
    document.body.style.paddingBottom = '80px';

    if (!this.eventSent.start && mediaId) {
      apiPost('/api/event', { event_type: 'audio_start', media_id: Number(mediaId) });
      this.eventSent.start = true;
    }
  },

  togglePlay() {
    if (!this.audio) return;
    if (this.audio.paused) {
      this.audio.play();
      this.playPauseBtn.textContent = '⏸';
    } else {
      this.audio.pause();
      this.playPauseBtn.textContent = '▶';
    }
  },

  _fmt(s) {
    if (!s || isNaN(s)) return '0:00';
    const m = Math.floor(s / 60), sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2,'0')}`;
  },

  _checkProgress(current, duration) {
    if (!duration || !this.mediaId) return;
    const pct = (current / duration) * 100;
    if (!this.eventSent.progress25 && pct >= 25) {
      apiPost('/api/event', { event_type: 'video_progress', media_id: Number(this.mediaId), meta: { pct: 25 } });
      this.eventSent.progress25 = true;
    }
    if (!this.eventSent.progress50 && pct >= 50) {
      apiPost('/api/event', { event_type: 'video_progress', media_id: Number(this.mediaId), meta: { pct: 50 } });
      this.eventSent.progress50 = true;
    }
    if (!this.eventSent.progress75 && pct >= 75) {
      apiPost('/api/event', { event_type: 'video_progress', media_id: Number(this.mediaId), meta: { pct: 75 } });
      this.eventSent.progress75 = true;
    }
  },
};

/* ============================================================
   Video Player Events
   ============================================================ */
function initVideoPlayer() {
  const video   = document.getElementById('main-video');
  const mediaId = video?.dataset.mediaId;
  if (!video || !mediaId) return;

  let started = false, completed = false;
  const sentProgress = {};

  video.addEventListener('play', () => {
    if (!started) {
      apiPost('/api/event', { event_type: 'video_start', media_id: Number(mediaId) });
      started = true;
    }
  });

  video.addEventListener('timeupdate', () => {
    const { currentTime, duration } = video;
    if (!duration) return;
    const pct = Math.floor((currentTime / duration) * 100);
    [25, 50, 75].forEach(p => {
      if (pct >= p && !sentProgress[p]) {
        apiPost('/api/event', { event_type: 'video_progress', media_id: Number(mediaId), meta: { pct: p } });
        sentProgress[p] = true;
      }
    });
  });

  video.addEventListener('ended', () => {
    if (!completed) {
      apiPost('/api/event', { event_type: 'video_complete', media_id: Number(mediaId) });
      completed = true;
    }
  });
}

/* ============================================================
   Drag-and-drop Upload Zone
   ============================================================ */
function initUploadZone() {
  const zone     = document.getElementById('upload-zone');
  const input    = document.getElementById('media-file-input');
  const preview  = document.getElementById('file-preview');
  const filename = document.getElementById('chosen-filename');
  if (!zone || !input) return;

  ['dragenter','dragover'].forEach(ev => {
    zone.addEventListener(ev, e => {
      e.preventDefault();
      zone.classList.add('drag-over');
    });
  });
  ['dragleave','drop'].forEach(ev => {
    zone.addEventListener(ev, e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
    });
  });
  zone.addEventListener('drop', e => {
    const file = e.dataTransfer.files[0];
    if (file) _handleFileSelect(file);
  });
  input.addEventListener('change', () => {
    if (input.files[0]) _handleFileSelect(input.files[0]);
  });

  function _handleFileSelect(file) {
    if (filename) filename.textContent = file.name;
    // Preview
    if (preview && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = e => {
        preview.src = e.target.result;
        preview.style.display = 'block';
      };
      reader.readAsDataURL(file);
    }
  }
}

/* ============================================================
   Thumbnail Preview
   ============================================================ */
function initThumbnailPreview() {
  const thumbInput   = document.getElementById('thumbnail-input');
  const thumbPreview = document.getElementById('thumb-preview');
  if (!thumbInput || !thumbPreview) return;
  thumbInput.addEventListener('change', () => {
    const file = thumbInput.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = e => {
        thumbPreview.src   = e.target.result;
        thumbPreview.style.display = 'block';
      };
      reader.readAsDataURL(file);
    }
  });
}

/* ============================================================
   Bulk Select
   ============================================================ */
function initBulkSelect() {
  const selectAll  = document.getElementById('select-all');
  const checkboxes = document.querySelectorAll('.media-select-cb');
  const bulkBar    = document.getElementById('bulk-bar');
  const countEl    = document.getElementById('bulk-count-text');

  if (!selectAll) return;

  function updateBar() {
    const checked = document.querySelectorAll('.media-select-cb:checked').length;
    if (bulkBar) bulkBar.classList.toggle('visible', checked > 0);
    if (countEl) countEl.textContent = `${checked} item${checked !== 1 ? 's' : ''} selected`;
  }

  selectAll.addEventListener('change', () => {
    checkboxes.forEach(cb => { cb.checked = selectAll.checked; });
    updateBar();
  });
  checkboxes.forEach(cb => {
    cb.addEventListener('change', updateBar);
  });
}

/* ============================================================
   Alert dismissal
   ============================================================ */
function initAlerts() {
  document.querySelectorAll('.alert-close').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.alert')?.remove();
    });
  });
}

/* ============================================================
   Confirm dialogs
   ============================================================ */
function initConfirm() {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      const msg = el.dataset.confirm || 'Are you sure?';
      if (!confirm(msg)) e.preventDefault();
    });
  });
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', e => {
      const msg = form.dataset.confirm || 'Are you sure?';
      if (!confirm(msg)) e.preventDefault();
    });
  });
}

/* ============================================================
   Copy to clipboard
   ============================================================ */
function initCopyButtons() {
  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.addEventListener('click', () => {
      const text = btn.dataset.copy;
      navigator.clipboard.writeText(text).then(() => {
        ToastManager.show('Copied!', 'success', 2000);
      });
    });
  });
}

/* ============================================================
   Folder card edit modal (inline)
   ============================================================ */
function openFolderEdit(id, name, desc, visibility) {
  document.getElementById('edit-folder-id').value          = id;
  document.getElementById('edit-folder-name').value        = name;
  document.getElementById('edit-folder-desc').value        = desc;
  document.getElementById('edit-folder-visibility').value  = visibility;
  openModal('folder-edit-modal');
}

/* ============================================================
   Modal helpers
   ============================================================ */
function openModal(id) {
  document.getElementById(id)?.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeModal(id) {
  document.getElementById(id)?.classList.remove('open');
  document.body.style.overflow = '';
}
// Close on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
    document.body.style.overflow = '';
  }
});

/* ============================================================
   Gallery search (debounce)
   ============================================================ */
function initGallerySearch() {
  const form = document.getElementById('gallery-search-form');
  const inp  = document.getElementById('gallery-search-input');
  if (!form || !inp) return;
  let timer;
  inp.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => form.submit(), 500);
  });
}

/* ============================================================
   Lazy loading (Intersection Observer)
   ============================================================ */
function initLazyLoad() {
  const imgs = document.querySelectorAll('img[data-src]');
  if (!imgs.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
        io.unobserve(img);
      }
    });
  }, { rootMargin: '200px' });
  imgs.forEach(img => io.observe(img));
}

/* ============================================================
   Init on DOM ready
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initGalleryCards();
  initInteractions();
  initUploadZone();
  initThumbnailPreview();
  initBulkSelect();
  initAlerts();
  initConfirm();
  initCopyButtons();
  initGallerySearch();
  initLazyLoad();
  AudioPlayer.init();
  initVideoPlayer();

  // Auto-dismiss flash messages
  setTimeout(() => {
    document.querySelectorAll('.alert.auto-dismiss').forEach(el => {
      el.style.opacity = '0';
      el.style.transition = 'opacity .4s';
      setTimeout(() => el.remove(), 400);
    });
  }, 4000);
});
