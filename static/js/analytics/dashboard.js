(() => {
  const root = document.getElementById('analyticsDashboard');
  if (!root) return;

  const form = document.getElementById('analyticsFilters');
  const errorBox = document.getElementById('analyticsError');
  const exportLink = document.getElementById('exportCsv');
  const charts = {};
  const colors = ['#f27338', '#f7b955', '#56a36c', '#6f63bb', '#d76378'];

  const query = () => new URLSearchParams(new FormData(form)).toString();
  const chartUrl = (name, qs) => `${root.dataset.chartUrl.replace('__chart__', name)}?${qs}`;

  async function getJson(url) {
    const response = await fetch(url, {headers: {'Accept': 'application/json'}});
    const body = await response.json().catch(() => ({ok: false, error: 'Invalid server response.'}));
    if (!response.ok || !body.ok) throw new Error(body.error || 'Analytics could not be loaded.');
    return body;
  }

  function setKpis(kpis) {
    const values = {
      total_qr_scans: kpis.total_qr_scans,
      unique_customers: kpis.unique_customers,
      returning_customers: kpis.returning_customers,
      games_played: kpis.games_played,
      game_completion_rate: `${kpis.game_completion_rate}%`,
      coupons_generated: kpis.coupons_generated,
      coupons_redeemed: kpis.coupons_redeemed,
      redemption_rate: `${kpis.redemption_rate}%`,
    };
    Object.entries(values).forEach(([key, value]) => {
      document.getElementById(`kpi_${key}`).textContent = value;
    });
  }

  function renderChart(id, config) {
    const canvas = document.getElementById(id);
    const styles = getComputedStyle(document.documentElement);
    const textColor = styles.getPropertyValue('--text').trim() || '#211b2d';
    const borderColor = styles.getPropertyValue('--border').trim() || 'rgba(48,34,65,.1)';
    charts[id]?.destroy();
    charts[id] = new Chart(canvas, {
      ...config,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {mode: 'index', intersect: false},
        color: textColor,
        scales: config.type === 'doughnut' ? undefined : {
          x: {ticks: {color: textColor}, grid: {color: borderColor}},
          y: {beginAtZero: true, ticks: {color: textColor, precision: 0}, grid: {color: borderColor}},
        },
        plugins: {legend: {display: config.data.datasets.length > 1 || config.type === 'doughnut', labels: {color: textColor}}},
        ...config.options,
      },
    });
  }

  function line(id, rows, label, color = colors[0]) {
    renderChart(id, {type: 'line', data: {labels: rows.map(row => row.date), datasets: [{label, data: rows.map(row => row.count), borderColor: color, backgroundColor: `${color}22`, fill: true, tension: .3}]}});
  }

  function doughnut(id, rows, labelKey) {
    const safeRows = rows.length ? rows : [{[labelKey]: 'No data', count: 0}];
    renderChart(id, {type: 'doughnut', data: {labels: safeRows.map(row => row[labelKey]), datasets: [{data: safeRows.map(row => row.count), backgroundColor: colors}]}});
  }

  async function load() {
    errorBox.hidden = true;
    form.setAttribute('aria-busy', 'true');
    const qs = query();
    exportLink.href = `${root.dataset.exportUrl}?${qs}`;
    try {
      const names = ['daily_scans', 'daily_games', 'daily_coupons', 'daily_redemptions', 'popular_games', 'device_breakdown', 'peak_hours'];
      const [overview, ...responses] = await Promise.all([
        getJson(`${root.dataset.overviewUrl}?${qs}`),
        ...names.map(name => getJson(chartUrl(name, qs))),
      ]);
      const data = Object.fromEntries(names.map((name, index) => [name, responses[index].data]));
      setKpis(overview.kpis);
      line('chart_daily_scans', data.daily_scans, 'QR scans');
      line('chart_daily_games', data.daily_games, 'Games played', colors[3]);
      renderChart('chart_coupons', {type: 'line', data: {labels: data.daily_coupons.map(row => row.date), datasets: [
        {label: 'Generated', data: data.daily_coupons.map(row => row.count), borderColor: colors[1], tension: .3},
        {label: 'Redeemed', data: data.daily_redemptions.map(row => row.count), borderColor: colors[2], tension: .3},
      ]}});
      doughnut('chart_popular_games', data.popular_games, 'game');
      doughnut('chart_device_breakdown', data.device_breakdown, 'device');
      renderChart('chart_peak_hours', {type: 'bar', data: {labels: data.peak_hours.map(row => row.hour), datasets: [{label: 'QR scans', data: data.peak_hours.map(row => row.count), backgroundColor: colors[0]}]}});
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      form.removeAttribute('aria-busy');
    }
  }

  form.addEventListener('submit', event => { event.preventDefault(); load(); });
  new MutationObserver(mutations => {
    if (mutations.some(mutation => mutation.attributeName === 'data-bs-theme')) load();
  }).observe(document.documentElement, {attributes: true});
  load();
})();
