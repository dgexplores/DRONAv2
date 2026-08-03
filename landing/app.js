(function () {
  'use strict';

  // ===== CONFIG: point this at the live Railway app once deployed =====
  var SRMS_APP_URL = 'https://dronav2-production.up.railway.app';

  // Apply app URL to all CTA links
  document.querySelectorAll('[data-app-link]').forEach(function (el) {
    el.setAttribute('href', SRMS_APP_URL);
  });
  // =====================================================================

  // Nav shadow on scroll
  var nav = document.getElementById('nav');
  var onScroll = function () {
    if (window.scrollY > 10) nav.classList.add('scrolled');
    else nav.classList.remove('scrolled');
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // Mobile nav toggle
  var toggle = document.getElementById('navToggle');
  var links = document.querySelector('.nav-links');
  toggle.addEventListener('click', function () {
    var open = links.classList.toggle('open');
    toggle.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', open);
  });
  links.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () {
      links.classList.remove('open');
      toggle.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
})();
