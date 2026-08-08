(function () {
  'use strict';

  var STORAGE_KEY = 'playbite-theme';

  function getPreferredTheme() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    root.setAttribute('data-bs-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    });
  }

  applyTheme(getPreferredTheme());

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var next = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(next);
      });
    });

    document.querySelectorAll('.nav-link[href*="#"]').forEach(function (link) {
      var hash = link.hash;
      if (!hash || hash === '#') return;
      var target = document.querySelector(hash);
      if (!target) return;
      link.addEventListener('click', function (event) {
        if (link.pathname === window.location.pathname || link.getAttribute('href').startsWith('#')) {
          event.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          target.focus({ preventScroll: true });
        }
      });
    });

    document.querySelectorAll('.table-stack tbody td').forEach(function (cell) {
      var label = cell.closest('tr') && cell.cellIndex >= 0;
      var head = cell.closest('table') && cell.closest('table').querySelectorAll('thead th');
      if (head && head[cell.cellIndex]) {
        cell.setAttribute('data-label', head[cell.cellIndex].textContent.trim());
      }
    });

    document.querySelectorAll('img[loading="lazy"]').forEach(function (img) {
      img.addEventListener('error', function () {
        img.classList.add('d-none');
      });
    });
  });
})();

(function () {
  'use strict';

  function buildChartConfig(key, payload) {
    var colors = ['#FF8C00', '#FFC107', '#FFB347', '#FF6B6B', '#4ECDC4'];
    var base = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: key === 'coupon_redemption' || key === 'popular_games' } },
    };
    if (key === 'coupon_redemption' || key === 'popular_games') {
      return {
        type: 'doughnut',
        data: {
          labels: payload.labels,
          datasets: [{ data: payload.data, backgroundColor: colors }],
        },
        options: base,
      };
    }
    return {
      type: 'line',
      data: {
        labels: payload.labels,
        datasets: [{
          label: key.replace(/_/g, ' '),
          data: payload.data,
          borderColor: '#FF8C00',
          backgroundColor: 'rgba(255, 140, 0, 0.15)',
          tension: 0.35,
          fill: key === 'daily_plays' || key === 'peak_hours',
        }],
      },
      options: Object.assign({}, base, {
        scales: { y: { beginAtZero: true } },
      }),
    };
  }

  function initDashboardCharts() {
    var charts = window.__DASHBOARD_CHARTS__;
    if (!charts || !window.Chart) return;

    var map = {
      chartDailyPlays: 'daily_plays',
      chartWeeklyQr: 'weekly_qr',
      chartCoupon: 'coupon_redemption',
      chartPopularGames: 'popular_games',
      chartPeakHours: 'peak_hours',
    };

    Object.keys(map).forEach(function (id) {
      var canvas = document.getElementById(id);
      var key = map[id];
      if (!canvas || !charts[key]) return;
      var card = canvas.closest('.chart-card') || canvas.closest('.card');
      if (card) card.classList.remove('is-loading');
      new window.Chart(canvas, buildChartConfig(key, charts[key]));
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!window.__DASHBOARD_CHARTS__) return;
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
    script.async = true;
    script.onload = initDashboardCharts;
    document.head.appendChild(script);
  });
})();
