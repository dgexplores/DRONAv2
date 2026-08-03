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
    var saveTimer = null;

    function saveProgress(position, completed) {
      fetch(saveUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          position: position,
          completed: completed || false
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
        lastSaved = current;
        saveProgress(current, false);
      }
    });

    // Save on pause/end
    lessonVideo.addEventListener('pause', function () {
      saveProgress(Math.floor(lessonVideo.currentTime), false);
    });

    // Mark completed when video ends
    lessonVideo.addEventListener('ended', function () {
      saveProgress(Math.floor(lessonVideo.currentTime), true);
    });

    // Save on page unload
    window.addEventListener('beforeunload', function () {
      if (lessonVideo.currentTime > 0) {
        navigator.sendBeacon(saveUrl, new Blob([JSON.stringify({
          position: Math.floor(lessonVideo.currentTime),
          completed: false
        })], { type: 'application/json' }));
      }
    });
  }

  // Cookie helper for CSRF
  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

})();
