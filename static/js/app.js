// SRMS Drona - Main Application JS
(function () {
  'use strict';

  // PWA Service Worker Registration
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/static/sw.js')
        .then(function (reg) {
          console.log('[SW] Registered: ', reg.scope);
        })
        .catch(function (err) {
          console.warn('[SW] Registration failed: ', err);
        });
    });
  }

  // Video Progress Autosave
  var lessonVideo = document.getElementById('lesson-video');
  if (lessonVideo) {
    var lessonId = lessonVideo.getAttribute('data-lesson-id');
    var saveUrl = '/lessons/' + lessonId + '/progress/';
    var lastSaved = 0;
    var watchedSinceSave = 0;
    var saveTimer = null;

    function saveProgress(position, completed, watched) {
      fetch(saveUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          position: position,
          completed: completed || false,
          watched: watched || 0
        })
      }).then(function (resp) {
        return resp.json();
      }).then(function (data) {
        if (data.progress_percent !== undefined) {
          updateProgressBar(data.progress_percent);
        }
      }).catch(function (err) {
        console.error('Progress save error:', err);
      });
    }

    function updateProgressBar(percent) {
      var bars = document.querySelectorAll('[data-progress-percent]');
      bars.forEach(function (bar) {
        bar.style.width = percent + '%';
        var label = document.querySelector('[data-progress-text]');
        if (label) label.textContent = percent + '%';
      });
    }

    // Throttled progress save every 10 seconds
    lessonVideo.addEventListener('timeupdate', function () {
      var current = Math.floor(lessonVideo.currentTime);
      if (current - lastSaved >= 10) {
        watchedSinceSave = current - lastSaved;
        lastSaved = current;
        saveProgress(current, false, watchedSinceSave);
        watchedSinceSave = 0;
      }
    });

    // Save on pause/end
    lessonVideo.addEventListener('pause', function () {
      var current = Math.floor(lessonVideo.currentTime);
      saveProgress(current, false, watchedSinceSave);
      watchedSinceSave = 0;
    });

    // Mark completed when video ends
    lessonVideo.addEventListener('ended', function () {
      var current = Math.floor(lessonVideo.currentTime);
      saveProgress(current, true, watchedSinceSave);
      watchedSinceSave = 0;
    });

    // Save on page unload
    window.addEventListener('beforeunload', function () {
      if (lessonVideo.currentTime > 0) {
        navigator.sendBeacon(saveUrl, new Blob([JSON.stringify({
          position: Math.floor(lessonVideo.currentTime),
          completed: false,
          watched: watchedSinceSave
        })], { type: 'application/json' }));
      }
    });
  }

  // ===== Sidebar drawer (mobile) =====
  var sidebar = document.getElementById('sidebar');
  var menuToggle = document.getElementById('menuToggle');
  var backdrop = document.getElementById('sidebarBackdrop');

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('open');
    if (backdrop) backdrop.classList.add('show');
    if (menuToggle) menuToggle.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('show');
    if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  if (menuToggle) {
    menuToggle.addEventListener('click', function () {
      if (sidebar.classList.contains('open')) closeSidebar();
      else openSidebar();
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeSidebar);
  }

  // Close drawer when a nav link is tapped on mobile
  document.querySelectorAll('.sidebar-link').forEach(function (link) {
    link.addEventListener('click', function () {
      if (sidebar && sidebar.classList.contains('open')) closeSidebar();
    });
  });

  // Close drawer on resize back to desktop
  window.addEventListener('resize', function () {
    if (window.innerWidth > 900) closeSidebar();
  });

  // ===== Auto-dismiss alerts =====
  document.querySelectorAll('.alert-dismiss').forEach(function (alert) {
    setTimeout(function () {
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-6px)';
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      setTimeout(function () { alert.remove(); }, 450);
    }, 5000);
  });

  // Cookie helper for CSRF
  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  // ===== Scroll reveal (progressive enhancement) =====
  var revealEls = document.querySelectorAll('.reveal');
  if (revealEls.length) {
    if ('IntersectionObserver' in window &&
        window.matchMedia('(prefers-reduced-motion: no-preference)').matches) {
      var ro = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            ro.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
      revealEls.forEach(function (el) { ro.observe(el); });
    } else {
      revealEls.forEach(function (el) { el.classList.add('is-visible'); });
    }
  }

  // ===== Stat count-up =====
  document.querySelectorAll('[data-count]').forEach(function (el) {
    var raw = el.getAttribute('data-count').trim();
    var target = parseFloat(raw);
    if (isNaN(target)) return;
    var decimals = (raw.split('.')[1] || '').length;
    var suffix = el.textContent.replace(/[0-9.]/g, '');
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !('requestAnimationFrame' in window)) {
      el.textContent = target.toFixed(decimals) + suffix;
      return;
    }
    var dur = 700, start = null;
    function tick(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (eased * target).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });

})();
