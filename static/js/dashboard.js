/* static/js/dashboard.js
 * Lazy-load Chart.js and initialize charts using data from the
 * template context. Supports two embedding strategies:
 * 1) Global: window.dashboardCharts = [{id, type, data, options}, ...]
 *    where `id` is the canvas element id to render into.
 * 2) Per-canvas: <canvas id="..." data-chart='{...}'></canvas>
 *    where data-chart is JSON with {type, data, options}.
 *
 * The module watches canvases with an IntersectionObserver and only
 * loads Chart.js and renders a chart when the canvas comes into view.
 * Exposes DashboardCharts.init() for manual initialization if needed.
 */
(function (global) {
  'use strict';

  var CDN = 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js';
  var observer = null;
  var chartsToInit = new Map(); // canvasEl -> config
  var loaded = false;
  var loadingPromise = null;

  function safeJsonParse(str) {
    try {
      return JSON.parse(str);
    } catch (e) {
      console.warn('dashboard.js: failed to parse JSON', e);
      return null;
    }
  }

  function loadChartJs() {
    if (loaded) return Promise.resolve(window.Chart);
    if (loadingPromise) return loadingPromise;

    // If Chart already present, don't load.
    if (global.Chart) {
      loaded = true;
      return Promise.resolve(global.Chart);
    }

    loadingPromise = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = CDN;
      script.async = true;
      script.onload = function () {
        loaded = true;
        if (global.Chart) {
          resolve(global.Chart);
        } else {
          reject(new Error('Chart.js loaded but global Chart not found'));
        }
      };
      script.onerror = function (err) {
        reject(new Error('Failed to load Chart.js from CDN'));
      };
      document.head.appendChild(script);
    });

    return loadingPromise;
  }

  function createChartInstance(ChartConstructor, canvas, cfg) {
    // Chart.js v4 uses new Chart(canvas, cfg)
    try {
      // If the canvas was removed, bail out
      if (!document.body.contains(canvas)) return null;
      return new ChartConstructor(canvas, cfg);
    } catch (err) {
      console.error('dashboard.js: failed to create chart', err);
      return null;
    }
  }

  function normalizeConfig(raw) {
    if (!raw) return null;
    // Expect raw to contain: type, data, options
    // If user passed full Chart config already, use it.
    if (raw.type && raw.data) return {type: raw.type, data: raw.data, options: raw.options || {}};
    // If user passed `config` wrapper
    if (raw.config && raw.config.type && raw.config.data) return raw.config;
    return null;
  }

  function initCanvas(canvas) {
    // get config from data-chart attribute if present
    var dataAttr = canvas.getAttribute('data-chart');
    var cfg = null;
    if (dataAttr) {
      cfg = safeJsonParse(dataAttr);
      cfg = normalizeConfig(cfg);
    }

    // If there is a global dashboardCharts map, prefer that if it contains this id
    if ((!cfg || !cfg.type) && canvas.id && Array.isArray(global.dashboardCharts)) {
      var found = global.dashboardCharts.find(function (c) { return c.id === canvas.id; });
      if (found) cfg = normalizeConfig(found) || found;
    }

    // If still no config, nothing to do
    if (!cfg) return null;

    // store for later initialization
    chartsToInit.set(canvas, cfg);
    return cfg;
  }

  function onIntersection(entries) {
    var entriesToRender = [];
    entries.forEach(function (entry) {
      if (entry.isIntersecting || entry.intersectionRatio > 0) {
        var canvas = entry.target;
        if (chartsToInit.has(canvas)) entriesToRender.push(canvas);
      }
    });

    if (entriesToRender.length === 0) return;

    // Ensure Chart.js is loaded once a chart is about to render
    loadChartJs().then(function (ChartConstructor) {
      entriesToRender.forEach(function (canvas) {
        var cfg = chartsToInit.get(canvas);
        if (!cfg) return;

        // Create a shallow Chart config if needed
        var chartConfig = cfg.config || {type: cfg.type, data: cfg.data, options: cfg.options || {}};

        createChartInstance(ChartConstructor, canvas, chartConfig);

        // Once rendered, stop observing and remove from map
        if (observer) observer.unobserve(canvas);
        chartsToInit.delete(canvas);
      });
    }).catch(function (err) {
      console.error('dashboard.js: error loading Chart.js', err);
    });
  }

  function setupObserver() {
    if (observer) return observer;
    if (!('IntersectionObserver' in window)) {
      // Fallback: render all immediately
      observer = {
        observe: function () {},
        unobserve: function () {},
      };
      return observer;
    }

    observer = new IntersectionObserver(onIntersection, {root: null, rootMargin: '0px', threshold: 0.05});
    return observer;
  }

  function scanAndObserve(root) {
    root = root || document;
    // find canvases that either have data-chart attr or are referenced in window.dashboardCharts
    var selector = 'canvas[data-chart], canvas[id]';
    var nodes = Array.prototype.slice.call(root.querySelectorAll(selector));

    nodes.forEach(function (canvas) {
      // If already initialized, skip
      if (chartsToInit.has(canvas)) return;

      var hasConfig = initCanvas(canvas);
      if (hasConfig) {
        setupObserver().observe(canvas);
      } else {
        // Not all canvases with id necessarily have configs; if referenced in global but not yet present
        if (canvas.id && Array.isArray(global.dashboardCharts)) {
          var found = global.dashboardCharts.find(function (c) { return c.id === canvas.id; });
          if (found) {
            chartsToInit.set(canvas, normalizeConfig(found) || found);
            setupObserver().observe(canvas);
          }
        }
      }
    });
  }

  var DashboardCharts = {
    // Manually trigger initialization (e.g., call after AJAX content injection)
    init: function (opts) {
      // opts.root: optional root element to scan
      var root = opts && opts.root ? opts.root : document;
      scanAndObserve(root);

      // If IntersectionObserver not supported, load immediately for remaining items
      if (!('IntersectionObserver' in window)) {
        if (chartsToInit.size > 0) {
          loadChartJs().then(function (ChartConstructor) {
            chartsToInit.forEach(function (cfg, canvas) {
              var chartConfig = cfg.config || {type: cfg.type, data: cfg.data, options: cfg.options || {}};
              createChartInstance(ChartConstructor, canvas, chartConfig);
              chartsToInit.delete(canvas);
            });
          }).catch(function (err) { console.error(err); });
        }
      }
    },

    // For testing or callers that want to pre-load Chart.js without rendering
    preload: function () {
      return loadChartJs();
    },

    // Expose the internal map for debugging (read-only-ish)
    _pending: function () { return Array.from(chartsToInit.keys()); }
  };

  // Auto-init on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { DashboardCharts.init(); });
  } else {
    // DOM already ready
    setTimeout(function () { DashboardCharts.init(); }, 0);
  }

  // Attach to global
  global.DashboardCharts = DashboardCharts;

})(window);

