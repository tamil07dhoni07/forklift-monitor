// ================================================================
//  GEAR IQ — Dashboard script.js
//  Matched to api_server.py endpoints:
//
//  GET /api/vibration → { status, total_vibration, temperature,
//                         velocity:{x,y,z}, timestamp }
//  GET /api/voltages  → [{ sensor_id, voltage, current, power,
//                          energy, timestamp, status }]
//
//  /api/pressure and /api/hydraulic are not implemented yet —
//  those cards show "No Data" until you add those endpoints.
// ================================================================

const API        = 'http://localhost:5000/api';
const CAM_STREAM = 'http://127.0.0.1:8080/?action=stream';
const REFRESH_MS = 5000;   // poll every 5 seconds

// ── Thresholds ─────────────────────────────────────────────────
const THRESHOLDS = {
  motor: {
    tempWarn:  70,     // °C
    tempCrit:  90,
    vibWarn:   2.0,    // mm/s
    vibCrit:   3.5
  },
  battery: {
    levelLow:  30,     // %
    levelCrit: 15,
    cellLow:   11.5,   // V per cell
    voltMin:   11.8,   // V  → 0 %
    voltMax:   12.6    // V  → 100 %
  }
};

// ── DOM helpers ────────────────────────────────────────────────
const $ = id => document.getElementById(id);
function txt  (id, v)      { const e=$(id); if(e) e.textContent = v; }
function html_(id, v)      { const e=$(id); if(e) e.innerHTML   = v; }
function style_(id, p, v)  { const e=$(id); if(e) e.style[p]   = v; }
function attr_ (id, a, v)  { const e=$(id); if(e) e.setAttribute(a, v); }
function badge (id, lbl, color) {
  const e = $(id);
  if (!e) return;
  e.textContent = lbl;
  e.className   = `badge badge-${color}`;
}
function timeNow() {
  return new Date().toLocaleTimeString('en-US',
    { hour12: true, hour: 'numeric', minute: '2-digit' });
}

// ── Voltage → battery % ───────────────────────────────────────
function voltToPercent(v) {
  const { voltMin, voltMax } = THRESHOLDS.battery;
  return Math.max(0, Math.min(100, ((v - voltMin) / (voltMax - voltMin)) * 100));
}

// ── Derive health score from vibration ───────────────────────
//    (no health endpoint exists — calculated heuristic)
function vibToHealth(vib) {
  if (vib <= 0.5) return 95;
  if (vib <= 1.0) return 85;
  if (vib <= 2.0) return 72;
  if (vib <= 3.0) return 50;
  return Math.max(10, Math.round(50 - (vib - 3.0) * 15));
}


// ════════════════════════════════════════════════════════════════
//  BATTERY  ← /api/voltages
//  Fields used: sensor_id, voltage, current, power, energy, status
// ════════════════════════════════════════════════════════════════
function updateBattery(raw) {
  // If no data, show offline
  if (!raw || raw.length === 0) {
    txt('battery-percent', '--%');
    txt('battery-status',  '-- A');
    txt('bat-pct',         '--%');
    style_('battery-fill', 'height', '0%');
    style_('batt-bar',     'width',  '0%');
    ['bat1','bat2','bat3','bat4'].forEach(id => txt(id, '-- V'));
    txt('bat-power',  '-- W');
    txt('bat-energy', '-- Wh');
    badge('bat-badge', 'Offline', 'orange');
    return null;
  }

  const cells        = [0, 0, 0, 0];
  let   totalCurrent = 0;
  let   totalPower   = 0;
  let   totalEnergy  = 0;
  let   onlineCount  = 0;

  raw.forEach(r => {
    const i = parseInt(r.sensor_id) - 1;
    if (i >= 0 && i < 4) {
      cells[i]      = parseFloat(r.voltage) || 0;
      totalCurrent += parseFloat(r.current) || 0;
      totalPower   += parseFloat(r.power)   || 0;
      totalEnergy  += parseFloat(r.energy)  || 0;
      if (r.status === 'online') onlineCount++;
    }
  });

  const avg  = cells.reduce((a, c) => a + c, 0) / 4;
  const pct  = voltToPercent(avg);
  const pctR = Math.round(pct);

  txt('battery-percent', pctR + '%');
  txt('bat-pct',         pctR + '%');
  style_('battery-fill', 'height', pct + '%');
  style_('batt-bar',     'width',  pct + '%');
  txt('battery-status', totalCurrent.toFixed(1) + ' A');
  txt('bat-power',      totalPower.toFixed(1)   + ' W');
  txt('bat-energy',     totalEnergy.toFixed(2)  + ' Wh');

  // Individual cell voltages
  cells.forEach((v, i) =>
    txt(`bat${i + 1}`, v > 0 ? v.toFixed(2) + ' V' : '-- V'));

  // Status badge
  if      (onlineCount === 0)                         badge('bat-badge', 'Offline',  'orange');
  else if (pct < THRESHOLDS.battery.levelCrit)        badge('bat-badge', 'Critical', 'orange');
  else if (pct < THRESHOLDS.battery.levelLow)         badge('bat-badge', 'Low',      'orange');
  else                                                 badge('bat-badge', 'Normal',   'green');

  return { cells, avg, pct, totalCurrent, totalPower, totalEnergy };
}


// ════════════════════════════════════════════════════════════════
//  MOTOR  ← /api/vibration
//  Fields used: status, total_vibration, temperature, velocity{x,y,z}
// ════════════════════════════════════════════════════════════════
function updateMotor(raw) {
  if (!raw || raw.status === 'offline') {
    txt('motor-gauge-value',  '--');
    html_('motor-vib-total',  '-- <span class="u">mm/s</span>');
    html_('motor-velocity',   '--·--·-- <span class="u">mm/s</span>');
    txt('motor-health-score', '--/100');
    style_('motor-health-bar', 'width', '0%');
    attr_('motor-arc', 'stroke-dasharray', '0 166');
    badge('motor-badge', 'Offline', 'orange');
    return null;
  }

  const temp   = parseFloat(raw.temperature     || 0);
  const vib    = parseFloat(raw.total_vibration || 0);
  const vx     = parseFloat(raw.velocity?.x     || 0);
  const vy     = parseFloat(raw.velocity?.y     || 0);
  const vz     = parseFloat(raw.velocity?.z     || 0);
  const health = vibToHealth(vib);

  // Arc gauge fill (temperature, 0–150°C → 0–166 dasharray)
  const arcLen = Math.min((temp / 150) * 166, 166);
  attr_('motor-arc', 'stroke-dasharray', `${arcLen.toFixed(1)} 166`);

  txt('motor-gauge-value', Math.round(temp));
  html_('motor-vib-total',
        vib.toFixed(2) + ' <span class="u">mm/s</span>');
  html_('motor-velocity',
        `${vx.toFixed(2)}·${vy.toFixed(2)}·${vz.toFixed(2)} <span class="u">mm/s</span>`);
  txt('motor-health-score', health + '/100');
  style_('motor-health-bar', 'width', health + '%');

  // Status badge
  if      (temp > THRESHOLDS.motor.tempCrit || vib > THRESHOLDS.motor.vibCrit)
    badge('motor-badge', 'Critical', 'orange');
  else if (temp > THRESHOLDS.motor.tempWarn || vib > THRESHOLDS.motor.vibWarn)
    badge('motor-badge', 'Warm', 'orange');
  else
    badge('motor-badge', 'Normal', 'green');

  return { temp, vib, vx, vy, vz, health };
}


// ════════════════════════════════════════════════════════════════
//  PRESSURE  — no endpoint in api_server.py yet
//  Shows "No Data" until /api/pressure is implemented
// ════════════════════════════════════════════════════════════════
function updatePressure() {
  badge('pressure-badge', 'No Data', 'orange');
  txt('pressure-val', '--');
  attr_('pressure-fill',   'stroke-dasharray', '0 214');
  attr_('pressure-needle', 'transform', 'rotate(-90 80 92)');
  return null;
}


// ════════════════════════════════════════════════════════════════
//  HYDRAULIC OIL  — no endpoint in api_server.py yet
//  Shows "No Data" until /api/hydraulic is implemented
// ════════════════════════════════════════════════════════════════
function updateHydraulic() {
  badge('hyd-badge', 'No Data', 'orange');
  html_('hyd-level', '--<span class="u">%</span>');
  txt('hyd-temp',         '--');
  txt('hyd-quality-lbl',  '--');
  style_('hyd-quality-bar', 'width', '0%');
  // Empty the SVG tank
  attr_('hyd-fill', 'y',      '97');
  attr_('hyd-fill', 'height', '0');
  return null;
}


// ════════════════════════════════════════════════════════════════
//  KPI  — no /api/kpi endpoint exists
//  Energy is derived from battery voltage data (sum of all sensors)
//  Other metrics show "--" until dedicated endpoints are added
// ════════════════════════════════════════════════════════════════
function updateKPI(battResult) {
  txt('kpi-optime',   '--');    // needs /api/kpi
  txt('kpi-idletime', '--');    // needs /api/kpi
  txt('kpi-cycles',   '--');    // needs /api/kpi

  // Energy available from voltage sensor sum
  if (battResult && battResult.totalEnergy != null) {
    const kWh = (battResult.totalEnergy / 1000).toFixed(2);
    txt('kpi-energy', kWh > 0 ? kWh : battResult.totalEnergy.toFixed(1));
  } else {
    txt('kpi-energy', '--');
  }
}


// ════════════════════════════════════════════════════════════════
//  ALERTS  — generated from available sensor data only
// ════════════════════════════════════════════════════════════════
const WARN_SVG = `<svg width="18" height="18" viewBox="0 0 24 24" fill="#d97706">
  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
  <line x1="12" y1="9" x2="12" y2="13" stroke="#fff" stroke-width="1.5"/>
  <line x1="12" y1="17" x2="12.01" y2="17" stroke="#fff" stroke-width="2"/>
</svg>`;
const OK_SVG = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none">
  <circle cx="12" cy="12" r="10" fill="#16a34a"/>
  <polyline points="9,12 11,14 15,10" stroke="#fff" stroke-width="1.8" stroke-linecap="round" fill="none"/>
</svg>`;

function generateAlerts(motorR, battR) {
  const alerts = [];
  const t = timeNow();
  const T = THRESHOLDS;

  // ── Motor alerts ─────────────────────────────────────────────
  if (!motorR) {
    alerts.push({ type:'warn', msg:'Motor sensor offline', sub:'Check vibration sensor · ' + t });
  } else {
    // Vibration
    if      (motorR.vib > T.motor.vibCrit)
      alerts.push({ type:'warn', msg:'Motor vibration critical',  sub: motorR.vib.toFixed(2) + ' mm/s · ' + t });
    else if (motorR.vib > T.motor.vibWarn)
      alerts.push({ type:'warn', msg:'Motor vibration high',      sub: motorR.vib.toFixed(2) + ' mm/s · ' + t });

    // Temperature
    if      (motorR.temp > T.motor.tempCrit)
      alerts.push({ type:'warn', msg:'Motor temperature critical', sub: motorR.temp.toFixed(0) + '°C · ' + t });
    else if (motorR.temp > T.motor.tempWarn)
      alerts.push({ type:'warn', msg:'Motor temperature high',     sub: motorR.temp.toFixed(0) + '°C · ' + t });

    // All good
    if (motorR.vib <= T.motor.vibWarn && motorR.temp <= T.motor.tempWarn)
      alerts.push({ type:'ok', msg:'Motor operating normally', sub: t });
  }

  // ── Battery alerts ───────────────────────────────────────────
  if (!battR) {
    alerts.push({ type:'warn', msg:'Battery sensor offline', sub:'Check voltage sensors · ' + t });
  } else {
    // Overall level
    if      (battR.pct < T.battery.levelCrit)
      alerts.push({ type:'warn', msg:'Battery critically low',    sub: Math.round(battR.pct) + '% · ' + t });
    else if (battR.pct < T.battery.levelLow)
      alerts.push({ type:'warn', msg:'Battery level low',         sub: Math.round(battR.pct) + '% · ' + t });
    else
      alerts.push({ type:'ok',   msg:'Battery operating normally', sub: t });

    // Individual cell check
    battR.cells.forEach((v, i) => {
      if (v > 0 && v < T.battery.cellLow)
        alerts.push({ type:'warn', msg:`Cell B${i+1} low voltage`, sub: v.toFixed(2) + 'V · ' + t });
    });
  }

  // Final fallback
  if (!alerts.some(a => a.type === 'warn'))
    alerts.push({ type:'ok', msg:'All systems normal', sub: t });

  return alerts;
}

function renderAlerts(alerts) {
  const container = $('alerts-pills');
  if (!container) return;
  container.innerHTML = alerts.map(a => `
    <div class="alert-pill ${a.type === 'warn' ? 'a-warn' : 'a-ok'}">
      ${a.type === 'warn' ? WARN_SVG : OK_SVG}
      <div class="alert-body">
        <div class="alert-msg">${a.msg}</div>
        <div class="alert-sub">${a.sub}</div>
      </div>
    </div>`).join('');
}


// ════════════════════════════════════════════════════════════════
//  CAMERA  (MJPEG stream via <img>)
// ════════════════════════════════════════════════════════════════
function initCamera() {
  const modal    = $('camModal');
  const imgLarge = $('camVideoLarge');
  const expand   = $('camExpand');
  const close    = $('camClose');

  function openModal() {
    if (imgLarge) imgLarge.src = CAM_STREAM;
    if (modal)    modal.classList.add('open');
    document.addEventListener('keydown', escHandler);
  }
  function closeModal() {
    if (modal)    modal.classList.remove('open');
    if (imgLarge) imgLarge.src = '';   // stop bandwidth usage
    document.removeEventListener('keydown', escHandler);
  }
  function escHandler(e) { if (e.key === 'Escape') closeModal(); }

  if (expand) expand.addEventListener('click', openModal);
  if (close)  close.addEventListener('click',  closeModal);
  if (modal)  modal.addEventListener('click',  e => { if (e.target === modal) closeModal(); });
}


// ════════════════════════════════════════════════════════════════
//  FETCH + ORCHESTRATE
// ════════════════════════════════════════════════════════════════
async function safeFetch(url) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return await res.json();
  } catch (err) {
    console.warn('[GearIQ] Fetch failed:', url, '—', err.message);
    return null;
  }
}

async function fetchAll() {
  // Both requests fire in parallel
  const [vibRaw, voltRaw] = await Promise.all([
    safeFetch(`${API}/vibration`),
    safeFetch(`${API}/voltages`)
  ]);

  // Update each card
  const battResult  = updateBattery(voltRaw || []);
  const motorResult = updateMotor(vibRaw);
  updatePressure();    // No endpoint yet → shows "No Data"
  updateHydraulic();   // No endpoint yet → shows "No Data"
  updateKPI(battResult);

  // Build and render alerts
  const alerts = generateAlerts(motorResult, battResult);
  renderAlerts(alerts);
}


// ── Bootstrap ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initCamera();
  fetchAll();                        // immediate first load
  setInterval(fetchAll, REFRESH_MS); // then every 5 s
});