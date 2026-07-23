// ================================================================
//  GEAR IQ — script.js
//  Polls local API every 5 s → updates dashboard → sends to cloud
// ================================================================

// ── ① CONFIGURE ────────────────────────────────────────────────
const API           = 'http://localhost:5000/api';
const CAM_STREAM    = 'http://127.0.0.1:8080/?action=stream';
const REFRESH_MS    = 5000;
const CLOUD_API_URL = 'https://your-cloud-api.com/api/v1/ingest'; // ← change this
const CLOUD_API_KEY = 'your-api-key-here';                         // ← change this
const DEVICE_ID     = 'FL-2024';
const LOCATION      = 'Warehouse A — Bay 3';
// ───────────────────────────────────────────────────────────────

const THRESHOLDS = {
  motor:   { tempWarn:70, tempCrit:90, vibWarn:2.0, vibCrit:3.5 },
  battery: { levelLow:30, levelCrit:15, cellLow:11.5, voltMin:11.8, voltMax:12.6 }
};

// ── DOM helpers ─────────────────────────────────────────────────
const $      = id => document.getElementById(id);
const txt    = (id, v)    => { const e=$(id); if(e) e.textContent = v; };
const html_  = (id, v)    => { const e=$(id); if(e) e.innerHTML   = v; };
const style_ = (id, p, v) => { const e=$(id); if(e) e.style[p]   = v; };
const attr_  = (id, a, v) => { const e=$(id); if(e) e.setAttribute(a, v); };
function badge(id, lbl, color) {
  const e=$(id); if(!e) return;
  e.textContent=lbl; e.className=`badge badge-${color}`;
}
function timeNow() {
  return new Date().toLocaleTimeString('en-IN',
    { timeZone:'Asia/Kolkata', hour12:true, hour:'numeric', minute:'2-digit' });
}
function voltToPercent(v) {
  return Math.max(0, Math.min(100, ((v-THRESHOLDS.battery.voltMin)/(THRESHOLDS.battery.voltMax-THRESHOLDS.battery.voltMin))*100));
}
function vibToHealth(vib) {
  if(vib<=0.5) return 95; if(vib<=1.0) return 85;
  if(vib<=2.0) return 72; if(vib<=3.0) return 50;
  return Math.max(10, Math.round(50-(vib-3.0)*15));
}

// ── Network status ──────────────────────────────────────────────
function setNetPill(state, label) {
  const p=$('netPill'), l=$('netLabel');
  if(p) p.className=`net-pill ${state}`;
  if(l) l.textContent=label;
}
function setSensorDot(id, online) {
  const d=$(id); if(d) d.className=`sensor-dot ${online?'online':'offline'}`;
}
function setCloudDot(ok) {
  const d=$('cloudDot'), l=$('cloudLabel');
  if(d) d.className=`sensor-dot ${ok?'online':'offline'}`;
  if(l) l.textContent=ok?'Cloud':'Cloud ✗';
}

async function updateTemperature() {
    try {
        const res  = await safeFetch(`${API}/temperature`);
        if (!res || !res.length) return;

        res.forEach(r => {
            const el = document.getElementById(`bat${r.sensor_id}tmp`);
            if (!el) return;

            const temp   = parseFloat(r.temperature).toFixed(1);
            el.textContent = `${temp} °C`;

            // Color code: green normal / orange warm / red hot
            if      (r.temperature > 45) el.style.color = '#ef4444';  // red
            else if (r.temperature > 35) el.style.color = '#f97316';  // orange
            else                         el.style.color = 'rgba(255, 0, 0, 0.6)'; // normal
        });

    } catch (e) {
        console.warn('[Temperature] fetch failed →', e.message);
    }
}

// ════════════════════════════════════════════════════════════════
//  BATTERY  ← /api/voltages
// ════════════════════════════════════════════════════════════════
function updateBattery(raw) {
  if (!raw || !raw.length) {
    // txt('battery-percent','--%'); txt('battery-status','-- A');
    // txt('bat-pct','--%'); txt('bat-power','-- W'); txt('bat-energy','-- Wh');
    // style_('battery-fill','height','0%'); style_('batt-bar','width','0%');
    // ['bat1','bat2','bat3','bat4'].forEach(id=>txt(id,'-- V'));
    // ['bat1tmp','bat2tmp','bat3tmp','bat4tmp'].forEach(id=>txt(id,'-- °C'));
    // badge('bat-badge','Offline','red'); return null;
  }
  // const cells=[0,0,0,0]; let cur=0, pwr=0, enrg=0, on=0;
  // raw.forEach(r=>{
  //   const i=parseInt(r.sensor_id)-1;
  //   if(i>=0&&i<4){ cells[i]=parseFloat(r.voltage)||0; }
  //   cur  += parseFloat(r.current)||0;
  //   pwr  += parseFloat(r.power)  ||0;
  //   enrg += parseFloat(r.energy) ||0;
  //   if(r.status==='online') on++;
  // });

  const sensorMap = {
  2: 0,
  3: 1,
  4: 2,
  6: 3
};

const cells = [0, 0, 0, 0];
let cur = 0, pwr = 0, enrg = 0, on = 0;

raw.forEach(r => {
  const idx = sensorMap[r.sensor_id];

  if (idx !== undefined) {
    cells[idx] = parseFloat(r.voltage) || 0;
  }

  cur += parseFloat(r.current) || 0;
  pwr += parseFloat(r.power) || 0;
  enrg += parseFloat(r.energy) || 0;

  if (r.status === "online") on++;
});

console.log(cells);

  const avg=cells.reduce((a,c)=>a+c,0)/4;
  const pct=voltToPercent(avg), pctR=Math.round(pct);
  txt('battery-percent',pctR+'%'); txt('bat-pct',pctR+'%');
  style_('battery-fill','height',pct+'%'); style_('batt-bar','width',pct+'%');
  txt('battery-status', cur.toFixed(1)+' A');
  txt('bat-power', pwr.toFixed(1)+' W'); txt('bat-energy', enrg.toFixed(2)+' Wh');
  cells.forEach((v,i)=>txt(`bat${i+1}`,v>0?v.toFixed(2)+' V':'-- V'));
  if(!on)         badge('bat-badge','Offline','red');
  else if(pct<THRESHOLDS.battery.levelCrit) badge('bat-badge','Critical','orange');
  else if(pct<THRESHOLDS.battery.levelLow)  badge('bat-badge','Low','orange');
  else badge('bat-badge','Normal','green');
  return { cells, avg, pct, totalCurrent:cur, totalPower:pwr, totalEnergy:enrg };
}

// ════════════════════════════════════════════════════════════════
//  MOTOR  ← /api/vibration
// ════════════════════════════════════════════════════════════════
function updateMotor(raw) {
  if(!raw||raw.status==='offline') {
    txt('motor-gauge-value','--');
    html_('motor-vib-total','-- <span class="u">mm/s</span>');
    html_('motor-velocity','--·--·-- <span class="u">mm/s</span>');
    txt('motor-health-score','--/100');
    style_('motor-health-bar','width','0%');
    attr_('motor-arc','stroke-dasharray','0 166');
    badge('motor-badge','Offline','red'); return null;
  }
  const temp=parseFloat(raw.temperature||0);
  const vib =parseFloat(raw.total_vibration||0);
  const vx  =parseFloat(raw.velocity?.x||0);
  const vy  =parseFloat(raw.velocity?.y||0);
  const vz  =parseFloat(raw.velocity?.z||0);
  const h   =vibToHealth(vib);
  attr_('motor-arc','stroke-dasharray',`${Math.min((temp/150)*166,166).toFixed(1)} 166`);
  txt('motor-gauge-value',Math.round(temp));
  html_('motor-vib-total',vib.toFixed(0)+' <span class="u">mm/s</span>');
  html_('motor-velocity',`${vx.toFixed(0)}·${vy.toFixed(0)}·${vz.toFixed(0)} <span class="u">mm/s</span>`);
  txt('motor-health-score',h+'/100');
  style_('motor-health-bar','width',h+'%');
  const T=THRESHOLDS.motor;
  if(temp>T.tempCrit||vib>T.vibCrit) badge('motor-badge','Critical','orange');
  else if(temp>T.tempWarn||vib>T.vibWarn) badge('motor-badge','Warm','orange');
  else badge('motor-badge','Normal','green');

  document.getElementById('motor-thermal-fill').style.height = `${(temp / 120) * 100}%`; // 45°C / 120°C
  document.getElementById('motor-gauge-val').textContent = temp.toFixed(0);
  return { temp, vib, vx, vy, vz, health:h };
}

// ════════════════════════════════════════════════════════════════
//  HYDRAULIC OIL  — no endpoint yet
// ════════════════════════════════════════════════════════════════
// function updateHydraulic() {
//   badge('hyd-badge','No Data','red');
//   html_('hyd-level','--<span class="u">%</span>');
//   txt('hyd-temp','--'); txt('hyd-quality-lbl','--');
//   style_('hyd-fill','width','0%');
//   //attr_('hyd-fill','y','97'); attr_('hyd-fill','height','0');
// }

async function updateHydraulic() {
    const data = await safeFetch(`${API}/hydraulic`);

    if (!data || data.status === 'offline') {
        badge('hyd-badge', 'No Data', 'orange');
        html_('hyd-level', '--<span class="u">%</span>');
        txt('hyd-temp', '--');
        txt('hyd-volume', '--');
        // attr_('hyd-fill', 'y',      '97');
        // attr_('hyd-fill', 'height', '0');
        style_('hyd-fill','width',0+'%');
        return;
    }

    const level = data.level_pct;
    const temp  = data.temperature;
    const vol   = data.volume_l;

    // SVG tank fill (rect y="3" height="94")
    const fillH = (level / 100) * 94;
    const fillY = 3 + 94 - fillH;
    // attr_('hyd-fill', 'y',      fillY.toFixed(1));
    // attr_('hyd-fill', 'height', fillH.toFixed(1));
    style_('hyd-fill','width',level+'%'); 
    // Values
    html_('hyd-level',  `${level.toFixed(1)}<span class="u">%</span>`);
    txt('hyd-temp',   temp.toFixed(1)+' °C');
    txt('hyd-volume', vol.toFixed(2) + ' L');

    // Badge
    if      (level < 20) badge('hyd-badge', 'Critical', 'orange');
    else if (level < 40) badge('hyd-badge', 'Low',      'orange');
    else                 badge('hyd-badge', 'Good',     'teal');

    // Temp color
    const tempTag = $('hyd-temp-tag');
    if (tempTag) {
        tempTag.textContent = temp > 65 ? 'High' : 'Normal';
        tempTag.style.color = temp > 65 ? '#f97316' : '';
    }

    console.log(`[Hydraulic] ✅ level=${level}%  temp=${temp}°C  volume=${vol}L`);
}

// ════════════════════════════════════════════════════════════════
//  KPI
// ════════════════════════════════════════════════════════════════
// function updateKPI(battResult) {
//   txt('kpi-optime','--'); txt('kpi-idletime','--'); txt('kpi-cycles','--');
//   txt('kpi-energy', battResult ? (battResult.totalEnergy/1000).toFixed(2) : '--');
// }

async function updateKPI() {
  const data = await safeFetch(`${API}/kpi`);

  if (!data) {
    txt('kpi-optime',   '--');
    txt('kpi-idletime', '--');
    txt('kpi-cycles',   '--');
    txt('kpi-energy',   '--');
    return;
  }

  txt('kpi-optime',   parseFloat(data.operating_time).toFixed(2));
  txt('kpi-idletime', parseFloat(data.idle_time).toFixed(2));
  txt('kpi-cycles',   data.cycles_today);
  txt('kpi-energy',   parseFloat(data.energy_used).toFixed(3));

  console.log(`[KPI] ✅ op=${data.operating_time}hrs  idle=${data.idle_time}hrs  cycles=${data.cycles_today}  energy=${data.energy_used}kWh`);
}

// ════════════════════════════════════════════════════════════════
//  ALERTS
// ════════════════════════════════════════════════════════════════
// SVG icons
const CRIT_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="#ef4444">
  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
  <line x1="12" y1="9" x2="12" y2="13" stroke="#fff" stroke-width="1.5"/>
  <line x1="12" y1="17" x2="12.01" y2="17" stroke="#fff" stroke-width="2"/>
</svg>`;
 
const WARN_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="#f59e0b">
  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
  <line x1="12" y1="9" x2="12" y2="13" stroke="#fff" stroke-width="1.5"/>
  <line x1="12" y1="17" x2="12.01" y2="17" stroke="#fff" stroke-width="2"/>
</svg>`;
 
const OK_SVG = `<svg width="15" height="15" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="#10b981"/>
  <polyline points="9,12 11,14 15,10" stroke="#fff" stroke-width="1.8"
    stroke-linecap="round" fill="none"/>
</svg>`;

function generateAlerts(mR, bR) {
  const a=[], t=timeNow(), T=THRESHOLDS;
  if(!mR) { a.push({type:'warn',msg:'Motor sensor offline',sub:'Check sensor · '+t}); }
  else {
    if(mR.vib>T.motor.vibCrit)  a.push({type:'warn',msg:'Motor vibration critical',sub:mR.vib.toFixed(2)+' mm/s · '+t});
    else if(mR.vib>T.motor.vibWarn) a.push({type:'warn',msg:'Motor vibration high',sub:mR.vib.toFixed(2)+' mm/s · '+t});
    if(mR.temp>T.motor.tempCrit) a.push({type:'warn',msg:'Motor temperature critical',sub:mR.temp.toFixed(0)+'°C · '+t});
    else if(mR.temp>T.motor.tempWarn) a.push({type:'warn',msg:'Motor temperature high',sub:mR.temp.toFixed(0)+'°C · '+t});
    if(mR.vib<=T.motor.vibWarn&&mR.temp<=T.motor.tempWarn) a.push({type:'ok',msg:'Motor operating normally',sub:t});
  }
  if(!bR) { a.push({type:'warn',msg:'Battery sensor offline',sub:'Check sensors · '+t}); }
  else {
    if(bR.pct<T.battery.levelCrit)      a.push({type:'warn',msg:'Battery critically low',sub:Math.round(bR.pct)+'% · '+t});
    else if(bR.pct<T.battery.levelLow)  a.push({type:'warn',msg:'Battery level low',sub:Math.round(bR.pct)+'% · '+t});
    else a.push({type:'ok',msg:'Battery operating normally',sub:t});
    bR.cells.forEach((v,i)=>{ if(v>0&&v<T.battery.cellLow) a.push({type:'warn',msg:`Cell B${i+1} low voltage`,sub:v.toFixed(2)+'V · '+t}); });
  }
  if(!a.some(x=>x.type==='warn')) a.push({type:'ok',msg:'All systems normal',sub:t});
  return a;
}
function renderAlerts(alerts) {
  const c=$('alerts-pills'); if(!c) return;
  c.innerHTML=alerts.map(a=>`
    <div class="alert-pill ${a.type==='warn'?'a-warn':'a-ok'}">
      ${a.type==='warn'?WARN_SVG:OK_SVG}
      <div class="alert-body">
        <div class="alert-msg">${a.msg}</div>
        <div class="alert-sub">${a.sub}</div>
      </div>
    </div>`).join('');
}

// ════════════════════════════════════════════════════════════════
//  ☁ CLOUD SYNC — sends snapshot every poll cycle
// ════════════════════════════════════════════════════════════════
async function syncToCloud(vibRaw, voltRaw, batt, motor) {
  if(!CLOUD_API_URL||CLOUD_API_URL.includes('your-cloud')) { setCloudDot(false); return; }
  const now=new Date().toLocaleString('sv-SE',{timeZone:'Asia/Kolkata'}).replace(' ','T')+'+05:30';
  const payload={
    device_id: DEVICE_ID, location: LOCATION, synced_at: now,
    record_count: { motor:vibRaw?1:0, battery:voltRaw?voltRaw.length:0, oil:0 },
    sensors: {
      motor: vibRaw ? [{
        total_vibration: parseFloat(vibRaw.total_vibration||0),
        temperature:     parseFloat(vibRaw.temperature||0),
        velocity: { x:parseFloat(vibRaw.velocity?.x||0), y:parseFloat(vibRaw.velocity?.y||0), z:parseFloat(vibRaw.velocity?.z||0) },
        status: vibRaw.status, recorded_at: vibRaw.timestamp||now
      }] : [],
      battery: (voltRaw||[]).map(r=>({
        sensor_id: r.sensor_id,
        voltage:   parseFloat(r.voltage||0), current: parseFloat(r.current||0),
        power:     parseFloat(r.power||0),   energy:  parseFloat(r.energy||0),
        status: r.status, recorded_at: r.timestamp||now
      })),
      oil: [],
      kpi: batt ? {
        battery_pct:   Math.round(batt.pct),
        total_current: parseFloat(batt.totalCurrent.toFixed(1)),
        total_power:   parseFloat(batt.totalPower.toFixed(1)),
        energy_kwh:    parseFloat((batt.totalEnergy/1000).toFixed(3))
      } : {}
    }
  };
  try {
    const res=await fetch(CLOUD_API_URL,{
      method:'POST',
      headers:{'Content-Type':'application/json','Authorization':`Bearer ${CLOUD_API_KEY}`,'X-Device-Id':DEVICE_ID},
      body:JSON.stringify(payload), keepalive:true, signal:AbortSignal.timeout(8000)
    });
    setCloudDot(res.ok);
    if(!res.ok) console.warn('[Cloud] HTTP',res.status);
  } catch(e) { setCloudDot(false); console.warn('[Cloud]',e.message); }
}

// ════════════════════════════════════════════════════════════════
//  API HEALTH CHECK
// ════════════════════════════════════════════════════════════════
async function checkApiHealth() {
  try {
    const r=await fetch(`${API}/health`,{signal:AbortSignal.timeout(3000)});
    if(r.ok){setNetPill('online','API Online');return true;}
    setNetPill('offline','API Error'); return false;
  } catch { setNetPill('offline','No Connection'); return false; }
}

// ════════════════════════════════════════════════════════════════
//  CAMERA MODAL
// ════════════════════════════════════════════════════════════════
function initCamera() {
  const modal=$('camModal'), imgL=$('camVideoLarge');
  const exp=$('camExpand'), cls=$('camClose');
  const open=()=>{ if(imgL) imgL.src=CAM_STREAM; if(modal) modal.classList.add('open'); document.addEventListener('keydown',esc); };
  const close=()=>{ if(modal) modal.classList.remove('open'); if(imgL) imgL.src=''; document.removeEventListener('keydown',esc); };
  const esc=e=>{ if(e.key==='Escape') close(); };
  if(exp) exp.addEventListener('click',open);
  if(cls) cls.addEventListener('click',close);
  if(modal) modal.addEventListener('click',e=>{ if(e.target===modal) close(); });
}

// ════════════════════════════════════════════════════════════════
//  MAIN FETCH LOOP
// ════════════════════════════════════════════════════════════════
async function safeFetch(url) {
  try {
    const r=await fetch(url,{signal:AbortSignal.timeout(4000)});
    if(!r.ok) throw new Error('HTTP '+r.status);
    return await r.json();
  } catch(e) { console.warn('[GearIQ]',url,e.message); return null; }
}

// ── DEVICE INFO ─────────────────────────────────────────────────
async function loadDeviceInfo() {
    try {
        const res = await fetch(`${API}/device`, { signal: AbortSignal.timeout(4000) });
        if (!res.ok) throw new Error('HTTP ' + res.status);

        const data = await res.json();

        // Update navbar elements
        const idEl  = document.getElementById('nav-id');
        const locEl = document.getElementById('nav-loc');
        const versionEl = document.getElementById('version');

        if (idEl)  idEl.textContent  = data.device_id || '--';
        if (locEl) locEl.textContent = data.location  || '--';
        if (versionEl) versionEl.textContent = 'Version - ' + (data.version || '--');

        // Also store globally for cloud sync payload
        window.DEVICE_ID = data.device_id;
        window.LOCATION  = data.location;

        console.log(`[Device] ID=${data.device_id}  Location=${data.location}`);

    } catch (e) {
        console.warn('[Device] Failed to load device info →', e.message);
    }
}



// async function fetchAll() {
//   const ok=await checkApiHealth();
//   if(!ok) {
//     setSensorDot('dotMotor',false); setSensorDot('dotBattery',false);
//     updateBattery([]); updateMotor(null); updateHydraulic(); updateKPI(null);
//     renderAlerts(generateAlerts(null,null)); setCloudDot(false); 
//    // await updateFaults(); 
//     //await updateTemperature();
//      return;
//   }
//   const [voltRaw,vibRaw]=await Promise.all([safeFetch(`${API}/voltages`),safeFetch(`${API}/vibration`)]);
//   setSensorDot('dotMotor',  !!(vibRaw&&vibRaw.status==='online'));
//   setSensorDot('dotBattery',!!(voltRaw&&voltRaw.some(r=>r.status==='online')));
//   const batt  = updateBattery(voltRaw||[]);
//   const motor = updateMotor(vibRaw);
//   updateHydraulic();
//   updateKPI(batt);
//   await updateTemperature(); 
//   renderAlerts(generateAlerts(motor,batt));
//   await updateFaults(); 
//   await syncToCloud(vibRaw,voltRaw,batt,motor);
// }

async function fetchAll() {
  console.log('─'.repeat(50));
  console.log(`[fetchAll] 🔄 Cycle started → ${new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })} IST`);

  // ── API Health ──────────────────────────────────────
  const ok = await checkApiHealth();
  if (!ok) {
    console.warn('[fetchAll] ❌ API offline → resetting all sensors');
    setSensorDot('dotMotor',   false);
    setSensorDot('dotBattery', false);
    updateBattery([]);
    updateMotor(null);
    updateHydraulic();
    updateKPI(null);
    console.log('[fetchAll] 🌡️  Fetching temperature ...');
    updateTemperature();
    renderAlerts(generateAlerts(null, null));
    setCloudDot(false);
    console.warn('[fetchAll] ⏳ Waiting for next cycle ...');
    return;
  }
  console.log('[fetchAll] ✅ API online');

  // ── Fetch sensors in parallel ───────────────────────
  console.log('[fetchAll] 📡 Fetching voltages + vibration in parallel ...');
  const [voltRaw, vibRaw] = await Promise.all([
    safeFetch(`${API}/voltages`),
    safeFetch(`${API}/vibration`)
  ]);

  console.log(`[fetchAll] 🔋 Voltages  → ${voltRaw ? voltRaw.length + ' sensor(s)' : 'null (fetch failed)'}`);
  console.log(`[fetchAll] 📳 Vibration → ${vibRaw  ? 'status=' + vibRaw.status + '  vib=' + vibRaw.total_vibration + ' mm/s  temp=' + vibRaw.temperature + '°C' : 'null (fetch failed)'}`);

  // ── Sensor status dots ──────────────────────────────
  const motorOnline   = !!(vibRaw  && vibRaw.status === 'online');
  const batteryOnline = !!(voltRaw && voltRaw.some(r => r.status === 'online'));
  setSensorDot('dotMotor',   motorOnline);
  setSensorDot('dotBattery', batteryOnline);
  console.log(`[fetchAll] 🟢 Motor=${motorOnline}  Battery=${batteryOnline}`);

  // ── Update cards ────────────────────────────────────
  console.log('[fetchAll] 🔋 Updating Battery card ...');
  const batt = updateBattery(voltRaw || []);
  console.log(`[fetchAll] 🔋 Battery → pct=${batt ? Math.round(batt.pct) + '%' : 'N/A'}  current=${batt ? batt.totalCurrent.toFixed(1) + 'A' : 'N/A'}`);

  console.log('[fetchAll] ⚙️  Updating Motor card ...');
  const motor = updateMotor(vibRaw);
  console.log(`[fetchAll] ⚙️  Motor → health=${motor ? motor.health + '/100' : 'N/A'}  vib=${motor ? motor.vib.toFixed(2) + ' mm/s' : 'N/A'}`);

  console.log('[fetchAll] 🛢️  Updating Hydraulic card ...');
  updateHydraulic();

  console.log('[fetchAll] 📊 Updating KPI tiles ...');
  updateKPI(batt);

  // ── Temperature ─────────────────────────────────────
  console.log('[fetchAll] 🌡️  Fetching temperature ...');
  await updateTemperature();

  // ── Alerts ──────────────────────────────────────────
  console.log('[fetchAll] 🔔 Generating alerts ...');
 // const alerts = generateAlerts(motor, batt);
  //renderAlerts(alerts);
  //const warnCount = alerts.filter(a => a.type === 'warn').length;
  //console.log(`[fetchAll] 🔔 Alerts → total=${alerts.length}  warnings=${warnCount}`);

  // ── Fault codes ─────────────────────────────────────
  console.log('[fetchAll] ⚠️  Checking fault codes ...');
 // await updateFaults();

  // ── Cloud sync ──────────────────────────────────────
  console.log('[fetchAll] ☁️  Syncing to cloud ...');
  await syncToCloud(vibRaw, voltRaw, batt, motor);

  console.log('[fetchAll] ✅ Cycle complete');
  console.log('─'.repeat(50));

  // Battery online
document.getElementById('bat-badge').className = 'panel-badge status-online';
document.getElementById('bat-badge').textContent = 'Online';

// Motor offline
document.getElementById('motor-badge').className = 'panel-badge status-offline';
document.getElementById('motor-badge').textContent = 'Offline';

// Hydraulic no data
document.getElementById('hyd-badge').className = 'panel-badge status-nodata';
document.getElementById('hyd-badge').textContent = 'No Data';
}

 
// ── Fetch and render faults ──────────────────────────────────────
async function updateFaults() {
    const data = await safeFetch(`${API}/faults`);
    if (!data) return;
 
    const container = $('alerts-pills');
    if (!container) return;
 
    // Update fault status indicator in navbar (optional)
    const statusEl = $('faultStatus');
    if (statusEl) {
        statusEl.textContent  = data.status;
        statusEl.style.color  = data.status === 'CRITICAL' ? '#ef4444'
                               : data.status === 'WARNING'  ? '#f59e0b'
                               : '#10b981';
    }
 
    // No faults → show all clear
    if (!data.faults || data.faults.length === 0) {
        container.innerHTML = `
          <div class="alert-pill a-ok">
            ${OK_SVG}
            <div class="alert-body">
              <div class="alert-msg">All systems normal</div>
              <div class="alert-sub">No active fault codes · ${timeNow()}</div>
            </div>
          </div>`;
        return;
    }
 
    // Render each fault as a pill
    container.innerHTML = data.faults.map(f => {
        const isCrit = f.severity === 'CRITICAL';
        const icon   = isCrit ? CRIT_SVG : WARN_SVG;
        const cls    = isCrit ? 'a-crit' : 'a-warn';
        return `
          <div class="alert-pill ${cls}" title="${f.gear_iq}">
            ${icon}
            <div class="alert-body">
              <div class="alert-msg">
                <span class="fault-code">${f.code}</span>
                ${f.oem_desc}
              </div>
              <div class="alert-sub">${f.value} · ${f.type} · ${f.time}</div>
            </div>
          </div>`;
    }).join('');
}

 


// ── Bootstrap ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded',()=>{
  loadDeviceInfo();  
  initCamera();
  window.addEventListener('offline',()=>setNetPill('offline','No Network'));
  window.addEventListener('online', ()=>setNetPill('checking','Reconnecting…'));
  setNetPill('checking','Connecting…'); setCloudDot(false);
  fetchAll();
  setInterval(fetchAll,REFRESH_MS);
});