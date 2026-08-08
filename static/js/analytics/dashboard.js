// analytics dashboard client
window.analyticsLoad = async function(opts){
  const start = opts.start; const end = opts.end;
  const qs = `?start=${start}&end=${end}`;
  // Overview KPIs
  const ov = await fetch(`/dashboard/analytics/api/overview/${qs}`);
  const j = await ov.json();
  if(!j.ok){ console.error('overview error', j); return; }
  const k = j.kpis;
  document.getElementById('kpi_total_qr_scans').innerText = k.total_qr_scans;
  document.getElementById('kpi_unique_customers').innerText = k.unique_customers;
  document.getElementById('kpi_games_played').innerText = k.games_played;
  document.getElementById('kpi_coupons_redeemed').innerText = k.coupons_redeemed;

  // charts
  const daily_scans_resp = await fetch(`/dashboard/analytics/api/chart/daily_scans/${qs}`);
  const daily_scans_json = await daily_scans_resp.json();
  if(daily_scans_json.ok){ renderLineChart('chart_daily_scans', daily_scans_json.data); }
  const daily_games_resp = await fetch(`/dashboard/analytics/api/chart/daily_games/${qs}`);
  const daily_games_json = await daily_games_resp.json();
  if(daily_games_json.ok){ renderLineChart('chart_daily_games', daily_games_json.data); }
  const popular_resp = await fetch(`/dashboard/analytics/api/chart/popular_games/${qs}`);
  const popular_json = await popular_resp.json();
  if(popular_json.ok){ renderPieChart('chart_popular_games', popular_json.data.map(d=>({label:d.game, value:d.count}))); }
  const device_resp = await fetch(`/dashboard/analytics/api/chart/device_breakdown/${qs}`);
  const device_json = await device_resp.json();
  if(device_json.ok){ renderPieChart('chart_device_breakdown', device_json.data.map(d=>({label:d.device, value:d.count}))); }
};

function renderLineChart(elId, data){
  const labels = data.map(d=>d.date);
  const vals = data.map(d=>d.count);
  const ctx = document.getElementById(elId).getContext('2d');
  if(window[elId+'_chart']) window[elId+'_chart'].destroy();
  window[elId+'_chart'] = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [{ label: 'Count', data: vals, fill: true, borderColor: '#FF8C00', backgroundColor: 'rgba(255,140,0,0.12)'}] },
    options: { responsive: true, interaction: {mode:'index',intersect:false} }
  });
}

function renderPieChart(elId, items){
  const labels = items.map(i=>i.label);
  const vals = items.map(i=>i.value);
  const ctx = document.getElementById(elId).getContext('2d');
  if(window[elId+'_chart']) window[elId+'_chart'].destroy();
  window[elId+'_chart'] = new Chart(ctx, {
    type: 'pie',
    data: { labels, datasets: [{ data: vals, backgroundColor: ['#FFB84D','#FFD966','#FF8C00','#FFC107','#FFE082'] }] },
    options: { responsive: true }
  });
}
