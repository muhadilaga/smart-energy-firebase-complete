import { initializeApp } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-app.js";
import { getAuth, signInWithEmailAndPassword, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";
import { getDatabase, ref, onValue, query, orderByKey, limitToLast } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-database.js";
import { firebaseConfig, DEVICE_ID } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getDatabase(app);
const devicePath = `devices/${DEVICE_ID}/latest`;

const els = {
  authLoading: document.getElementById("authLoading"),
  loginView: document.getElementById("loginView"),
  appView: document.getElementById("appView"),
  loginForm: document.getElementById("loginForm"),
  loginMsg: document.getElementById("loginMsg"),
  loginBtn: document.getElementById("loginBtn"),
  loginBtnText: document.querySelector("#loginBtn .btn-text"),
  loginSpinner: document.querySelector("#loginBtn .btn-spinner"),
  togglePasswordBtn: document.getElementById("togglePasswordBtn"),
  email: document.getElementById("email"),
  password: document.getElementById("password"),
  logoutBtn: document.getElementById("logoutBtn"),
  voltageValue: document.getElementById("voltageValue"),
  currentValue: document.getElementById("currentValue"),
  powerValue: document.getElementById("powerValue"),
  powerValueSmall: document.getElementById("powerValueSmall"),
  energyValue: document.getElementById("energyValue"),
  energyValueSmall: document.getElementById("energyValueSmall"),
  frequencyValue: document.getElementById("frequencyValue"),
  pfValue: document.getElementById("pfValue"),
  powerGaugeFill: document.getElementById("powerGaugeFill"),
  monitorPowerGaugeFill: document.getElementById("monitorPowerGaugeFill"),
  lastUpdateText: document.getElementById("lastUpdateText"),
  updatedAgo: document.getElementById("updatedAgo"),
  deviceStatus: document.getElementById("deviceStatus"),
  deviceStateLabel: document.getElementById("deviceStateLabel"),
  statusDot: document.getElementById("statusDot"),
  connectionValue: document.getElementById("connectionValue"),
  tariffValue: document.getElementById("tariffValue"),
  tariffDetail: document.getElementById("tariffDetail"),
  costBreakdown: document.getElementById("costBreakdown"),
  pzemBaselineWarning: document.getElementById("pzemBaselineWarning"),
  loadCostValue: document.getElementById("loadCostValue"),
  costValue: document.getElementById("costValue"),
  powerChart: document.getElementById("powerChart"),
  monitorStatusDot: document.getElementById("monitorStatusDot"),
  monitorStatusText: document.getElementById("monitorStatusText"),
  monitorLastUpdateText: document.getElementById("monitorLastUpdateText"),
  monitorUpdatedAgo: document.getElementById("monitorUpdatedAgo"),
  monitorPowerValue: document.getElementById("monitorPowerValue"),
  monitorVoltageValue: document.getElementById("monitorVoltageValue"),
  monitorCurrentValue: document.getElementById("monitorCurrentValue"),
  monitorPowerValueSmall: document.getElementById("monitorPowerValueSmall"),
  monitorEnergyValue: document.getElementById("monitorEnergyValue"),
  monitorFrequencyValue: document.getElementById("monitorFrequencyValue"),
  monitorPfValue: document.getElementById("monitorPfValue"),
  monitorPowerChart: document.getElementById("monitorPowerChart"),
  historySection: document.getElementById("historySection"),
  historyCount: document.getElementById("historyCount"),
  historyRange: document.getElementById("historyRange"),
  historyAvgPower: document.getElementById("historyAvgPower"),
  historyEnergySpan: document.getElementById("historyEnergySpan"),
  historyRangeFilter: document.getElementById("historyRangeFilter"),
  historyNotice: document.getElementById("historyNotice"),
  historyChartHint: document.getElementById("historyChartHint"),
  historyRowHint: document.getElementById("historyRowHint"),
  exportCsvBtn: document.getElementById("exportCsvBtn"),
  historyEmptyState: document.getElementById("historyEmptyState"),
  historyTableBody: document.getElementById("historyTableBody"),
  historyMobileList: document.getElementById("historyMobileList"),
  historyDesktopTableWrap: document.getElementById("historyDesktopTableWrap"),
  historyPowerChart: document.getElementById("historyPowerChart"),
  predictionSection: document.getElementById("predictionSection"),
  predictionModelStatus: document.getElementById("predictionModelStatus"),
  predictionHeroLabel: document.getElementById("predictionHeroLabel"),
  predictionEnergyNextHour: document.getElementById("predictionEnergyNextHour"),
  predictionHeroTitle: document.getElementById("predictionHeroTitle"),
  predictionHeroSubtext: document.getElementById("predictionHeroSubtext"),
  predictionTargetTimestamp: document.getElementById("predictionTargetTimestamp"),
  predictionFeatureTimestamp: document.getElementById("predictionFeatureTimestamp"),
  predictionStaleness: document.getElementById("predictionStaleness"),
  predictionModelVersion: document.getElementById("predictionModelVersion"),
  predictionRfUsed: document.getElementById("predictionRfUsed"),
  predictionMonthlyStatus: document.getElementById("predictionMonthlyStatus"),
  predictionObservedEnergy: document.getElementById("predictionObservedEnergy"),
  predictionObservedCost: document.getElementById("predictionObservedCost"),
  predictionPastEstimate: document.getElementById("predictionPastEstimate"),
  predictionRemainingEstimate: document.getElementById("predictionRemainingEstimate"),
  predictionRemainingCost: document.getElementById("predictionRemainingCost"),
  predictionMonthlyTotal: document.getElementById("predictionMonthlyTotal"),
  predictionMonthlyCost: document.getElementById("predictionMonthlyCost"),
  predictionProjectionMethod: document.getElementById("predictionProjectionMethod"),
  predictionWarning: document.getElementById("predictionWarning"),
  predictionCoverageWarning: document.getElementById("predictionCoverageWarning"),
  predictionBaselineMae: document.getElementById("predictionBaselineMae"),
  predictionBaselineRmse: document.getElementById("predictionBaselineRmse"),
  predictionBaselineR2: document.getElementById("predictionBaselineR2"),
  predictionMae: document.getElementById("predictionMae"),
  predictionRmse: document.getElementById("predictionRmse"),
  predictionR2: document.getElementById("predictionR2"),
  predictionEvalHint: document.getElementById("predictionEvalHint"),
  predictionMetricNote: document.getElementById("predictionMetricNote"),
  predictionResearchMinimum: document.getElementById("predictionResearchMinimum"),
  predictionFreshness: document.getElementById("predictionFreshness"),
  predictionDataQuality: document.getElementById("predictionDataQuality"),
  predictionEmptyState: document.getElementById("predictionEmptyState"),
  predictionGeneratedAt: document.getElementById("predictionGeneratedAt"),
  predictionSourceAge: document.getElementById("predictionSourceAge"),
  predictionEnergyLabel: document.getElementById("predictionEnergyLabel"),
  runPredictionBtn: document.getElementById("runPredictionBtn"),
  predictionRunStatus: document.getElementById("predictionRunStatus"),
  runPredictionBtnText: document.querySelector("#runPredictionBtn .prediction-run-btn__text"),
  runPredictionSpinner: document.querySelector("#runPredictionBtn .btn-spinner"),
  settingsSection: document.getElementById("settingsSection"),
  usageBeforeMonitoringInput: document.getElementById("usageBeforeMonitoringInput"),
  saveUsageBeforeBtn: document.getElementById("saveUsageBeforeBtn"),
  pzemEnergyBaselineInput: document.getElementById("pzemEnergyBaselineInput"),
  savePzemBaselineBtn: document.getElementById("savePzemBaselineBtn"),
  useCurrentPzemBtn: document.getElementById("useCurrentPzemBtn"),
  resetPzemBaselineBtn: document.getElementById("resetPzemBaselineBtn"),
  tariffInput: document.getElementById("tariffInput"),
  saveTariffBtn: document.getElementById("saveTariffBtn"),
  settingsMsg: document.getElementById("settingsMsg"),
  settingsDeviceStatus: document.getElementById("settingsDeviceStatus"),
  settingsAccountEmail: document.getElementById("settingsAccountEmail"),
  settingsModelStatus: document.getElementById("settingsModelStatus"),
  settingsLogoutBtn: document.getElementById("settingsLogoutBtn"),
  resetTariffBtn: document.getElementById("resetTariffBtn"),
  appTitle: document.querySelector(".topbar__title h1"),
  appSubtitle: document.querySelector(".topbar__title p"),
  navButtons: Array.from(document.querySelectorAll(".bottom-nav__item[data-page], .desktop-nav__item[data-page]")),
  dashboardSection: document.getElementById("dashboardSection"),
  monitoringSection: document.getElementById("monitoringSection"),
};

const chartState = { labels: [], values: [] };
const monitorChartState = { labels: [], values: [] };
const historyState = { all: [], filtered: [], filter: "1h", chart: null, loaded: false, unsubscribe: null };
const predictionState = { data: null, loaded: false, unsubscribe: null, liveGeneratedAt: null };
const chart = new Chart(els.powerChart, {
  type: "line",
  data: {
    labels: chartState.labels,
    datasets: [{
      label: "Daya (W)",
      data: chartState.values,
      borderColor: "#006b55",
      backgroundColor: "rgba(0,107,85,.12)",
      tension: 0.35,
      fill: true,
      pointRadius: 0,
      borderWidth: 2,
    }],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
      y: { beginAtZero: true },
    },
  },
});
const monitorChart = new Chart(els.monitorPowerChart, {
  type: "line",
  data: {
    labels: monitorChartState.labels,
    datasets: [{
      label: "Daya (W)",
      data: monitorChartState.values,
      borderColor: "#006b55",
      backgroundColor: "rgba(0,107,85,.12)",
      tension: 0.35,
      fill: true,
      pointRadius: 0,
      borderWidth: 2,
    }],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
      y: { beginAtZero: true },
    },
  },
});

let latestState = null;
let latestUnsubscribe = null;

// â”€â”€ Tarif bertingkat 450 VA Pascabayar R-1/TR â”€â”€
// Estimasi biaya merupakan nilai turunan dari konsumsi energi
// dan tidak digunakan sebagai target model Random Forest.
const TARIFF_PROFILE = {
  name: "450 VA Pascabayar",
  code: "R-1/TR",
  daya_va: 450,
  daya_kva: 0.45,
  biaya_beban_per_kva: 11000, // Rp/kVA/bulan
  blocks: [
    { limit: 30, rate: 169 },   // 0â€“30 kWh
    { limit: 60, rate: 360 },   // >30â€“60 kWh
    { limit: Infinity, rate: 495 }, // >60 kWh
  ],
};

function calculate450PostpaidEnergyCost(kwh) {
  if (!Number.isFinite(kwh) || kwh <= 0) return 0;
  let cost = 0;
  let remaining = kwh;
  let prevLimit = 0;
  for (const block of TARIFF_PROFILE.blocks) {
    const blockSize = block.limit - prevLimit;
    const used = Math.min(remaining, blockSize);
    cost += used * block.rate;
    remaining -= used;
    prevLimit = block.limit;
    if (remaining <= 0) break;
  }
  return cost;
}

function getUsageBeforeMonitoring() {
  const raw = localStorage.getItem("electricUsageBeforeMonitoring");
  if (raw === null || raw === "") return 0;
  const val = Number(raw);
  return (Number.isFinite(val) && val >= 0) ? val : 0;
}

function getPzemEnergyBaseline() {
  const raw = localStorage.getItem("pzemEnergyBaseline");
  if (raw === null || raw === "") return 0;
  const val = Number(raw);
  return (Number.isFinite(val) && val >= 0) ? val : 0;
}

function calculateMonitoredEnergy(rawPzemEnergy, baseline) {
  const raw = Number(rawPzemEnergy);
  const base = Number(baseline);
  if (!Number.isFinite(raw)) return { monitored: null, reset: false, diff: null };
  const safeBase = Number.isFinite(base) && base >= 0 ? base : 0;
  const diff = raw - safeBase;
  return { monitored: Math.max(0, diff), reset: diff < 0, diff };
}

function refreshLocalDerivedViews() {
  renderState(latestState);
  if (predictionState.data) setPredictionState(predictionState.data);
}

function fmtNumber(value, digits) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "--";
  return num.toFixed(digits);
}

function fmtMoney(value) {
  if (!Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(value);
}

function tieredCostLabel(kwh) {
  const energy = Number(kwh);
  if (!Number.isFinite(energy) || energy <= 0) return "â€”";
  return fmtMoney(calculate450PostpaidEnergyCost(energy));
}

function marginalCostLabel(currentUsageKwh, additionalKwh) {
  const cur = Number(currentUsageKwh);
  const add = Number(additionalKwh);
  if (!Number.isFinite(cur) || !Number.isFinite(add)) return "â€”";
  const total = Math.max(0, cur) + Math.max(0, add);
  const diff = calculate450PostpaidEnergyCost(total) - calculate450PostpaidEnergyCost(Math.max(0, cur));
  return diff >= 0 ? fmtMoney(diff) : "â€”";
}


function fmtDateTime(ms) {
  if (!Number.isFinite(ms)) return "--";
  return new Date(ms).toLocaleString("id-ID");
}

function timeAgo(ms) {
  const diff = Date.now() - ms;
  if (!Number.isFinite(diff) || diff < 0) return "--";
  if (diff < 60_000) return `${Math.max(1, Math.round(diff / 1000))} detik lalu`;
  const min = Math.round(diff / 60_000);
  return `${min} menit lalu`;
}

function setLoading(isLoading) {
  els.loginBtn.disabled = isLoading;
  els.loginSpinner.classList.toggle("hidden", !isLoading);
  els.loginBtnText.textContent = isLoading ? "Memproses..." : "Masuk";
}

function setLoginError(message) {
  els.loginMsg.textContent = message || "";
}

function updateChartPoint(label, value) {
  chartState.labels.push(label);
  chartState.values.push(value);
  if (chartState.labels.length > 60) {
    chartState.labels.shift();
    chartState.values.shift();
  }
  chart.update();
}

function updateMonitorChartPoint(label, value) {
  monitorChartState.labels.push(label);
  monitorChartState.values.push(value);
  if (monitorChartState.labels.length > 60) {
    monitorChartState.labels.shift();
    monitorChartState.values.shift();
  }
  monitorChart.update();
}

function initGauge() {
  const path = els.powerGaugeFill;
  if (!path || typeof path.getTotalLength !== 'function') return;
  const length = path.getTotalLength();
  path.style.strokeDasharray = `${length}`;
  path.style.strokeDashoffset = `${length}`;
}

function initMonitorGauge() {
  const path = els.monitorPowerGaugeFill;
  if (!path || typeof path.getTotalLength !== 'function') return;
  const length = path.getTotalLength();
  path.style.strokeDasharray = `${length}`;
  path.style.strokeDashoffset = `${length}`;
}

function setPowerGauge(path, percent) {
  if (!path || typeof path.getTotalLength !== 'function') return;
  const length = path.getTotalLength();
  path.style.strokeDasharray = `${length}`;
  path.style.strokeDashoffset = `${length * (1 - percent / 100)}`;
}

const HISTORY_MS = { "1h": 3600000, "6h": 21600000, "24h": 86400000, "7d": 604800000 };
function toFiniteNumber(value) { const n = Number(value); return Number.isFinite(n) ? n : null; }
function historyTimeFormat(ms, withSeconds = false) { if (!Number.isFinite(ms)) return "â€”"; return new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: withSeconds ? "2-digit" : undefined }).format(new Date(ms)); }
function historyDatePart(ms) { if (!Number.isFinite(ms)) return "â€”"; return new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", year: "numeric" }).format(new Date(ms)); }
function historyTimePart(ms) { if (!Number.isFinite(ms)) return "â€”"; return new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit" }).format(new Date(ms)); }
function parseHistorySnapshot(snap) { const out=[]; snap.forEach(child => { const val = child.val() || {}; const ts = toFiniteNumber(val.timestamp) ?? toFiniteNumber(child.key); if (!Number.isFinite(ts)) return; out.push({ key: child.key, timestamp: ts, voltage: toFiniteNumber(val.voltage), current: toFiniteNumber(val.current), power: toFiniteNumber(val.power), energy_kwh: toFiniteNumber(val.energy_kwh), frequency: toFiniteNumber(val.frequency), power_factor: toFiniteNumber(val.power_factor) }); }); out.sort((a,b)=>b.timestamp-a.timestamp); return out; }
function historyFilterLabel(key) { return key === "1h" ? "1 Jam" : key === "6h" ? "6 Jam" : key === "24h" ? "24 Jam" : "7 Hari"; }
function filterHistoryRecords(records, filterKey) { if (!records.length) return []; const latest = Math.max(...records.map(r=>r.timestamp).filter(Number.isFinite)); if (!Number.isFinite(latest)) return []; const cutoff = latest - (HISTORY_MS[filterKey] ?? HISTORY_MS["1h"]); return records.filter(r => r.timestamp >= cutoff); }
function renderHistory() { const all = historyState.all; if (!all.length) { historyState.filtered=[]; els.historyCount.textContent="â€”"; els.historyRange.textContent="â€”"; els.historyAvgPower.textContent="â€”"; els.historyEnergySpan.textContent="â€”"; els.historyRowHint.textContent="0 catatan"; els.historyNotice.textContent="Belum ada data riwayat."; els.historyEmptyState.classList.remove("hidden"); els.historyTableBody.innerHTML=""; els.historyMobileList.innerHTML=""; if (historyState.chart) { historyState.chart.data.labels=[]; historyState.chart.data.datasets[0].data=[]; historyState.chart.update(); } return; }
  const filtered = filterHistoryRecords(all, historyState.filter); historyState.filtered = filtered; const latest = all[0]; const oldest = all[all.length-1]; const coverage = latest.timestamp - oldest.timestamp; const requested = HISTORY_MS[historyState.filter] ?? HISTORY_MS["1h"]; const avgVals = filtered.map(r=>r.power).filter(v=>Number.isFinite(v)); const avgPower = avgVals.length ? avgVals.reduce((a,b)=>a+b,0)/avgVals.length : null; const firstEnergy = filtered.at(-1)?.energy_kwh; const lastEnergy = filtered[0]?.energy_kwh; const energySpan = Number.isFinite(firstEnergy) && Number.isFinite(lastEnergy) && lastEnergy >= firstEnergy ? lastEnergy - firstEnergy : null; const firstTs = filtered.at(-1)?.timestamp; const lastTs = filtered[0]?.timestamp; const sameDay = Number.isFinite(firstTs) && Number.isFinite(lastTs) && historyDatePart(firstTs) === historyDatePart(lastTs); els.historyCount.textContent = `${filtered.length} catatan`; els.historyRange.innerHTML = sameDay ? `${historyDatePart(firstTs)}<br><span>${historyTimePart(firstTs)} â€“ ${historyTimePart(lastTs)}</span>` : `${historyTimeFormat(firstTs)} â€“ ${historyTimeFormat(lastTs)}`; els.historyAvgPower.textContent = avgPower == null ? "â€”" : `${avgPower.toFixed(1)} W`; els.historyEnergySpan.textContent = energySpan == null ? "â€”" : `${energySpan.toFixed(4)} kWh`; els.historyRowHint.textContent = `${filtered.length} catatan`; els.historyNotice.textContent = coverage < requested ? `Data yang tersedia belum mencakup seluruh rentang ${historyFilterLabel(historyState.filter)}.` : `Menampilkan data ${historyFilterLabel(historyState.filter)}.`; els.historyChartHint.textContent = historyFilterLabel(historyState.filter); els.historyEmptyState.classList.toggle("hidden", filtered.length > 0); const rows = filtered.map(r => `<tr><td>${historyTimeFormat(r.timestamp)}</td><td>${r.voltage == null ? "â€”" : `${r.voltage.toFixed(1)} V`}</td><td>${r.current == null ? "â€”" : `${r.current.toFixed(3)} A`}</td><td>${r.power == null ? "â€”" : `${r.power.toFixed(1)} W`}</td><td>${r.energy_kwh == null ? "â€”" : `${r.energy_kwh.toFixed(4)} kWh`}</td><td>${r.frequency == null ? "â€”" : `${r.frequency.toFixed(1)} Hz`}</td><td>${r.power_factor == null ? "â€”" : r.power_factor.toFixed(2)}</td></tr>`).join(""); els.historyTableBody.innerHTML = rows; els.historyMobileList.innerHTML = filtered.map(r => `<article class="history-mobile-item"><div class="history-mobile-item__time">${historyTimeFormat(r.timestamp)}</div><div class="history-mobile-kv"><span>Daya</span><strong>${r.power == null ? "â€”" : `${r.power.toFixed(1)} W`}</strong><span>Tegangan</span><strong>${r.voltage == null ? "â€”" : `${r.voltage.toFixed(1)} V`}</strong><span>Arus</span><strong>${r.current == null ? "â€”" : `${r.current.toFixed(3)} A`}</strong><span>Energi</span><strong>${r.energy_kwh == null ? "â€”" : `${r.energy_kwh.toFixed(4)} kWh`}</strong><span>Frekuensi</span><strong>${r.frequency == null ? "â€”" : `${r.frequency.toFixed(1)} Hz`}</strong><span>Power Factor</span><strong>${r.power_factor == null ? "â€”" : r.power_factor.toFixed(2)}</strong></div></article>`).join(""); const chartData = filtered.slice().reverse().map(r=>({label:new Date(r.timestamp).toLocaleTimeString("id-ID", {hour:"2-digit", minute:"2-digit"}), value:r.power})); if (!historyState.chart) { historyState.chart = new Chart(els.historyPowerChart, { type:"line", data:{ labels: chartData.map(x=>x.label), datasets:[{ label:"Daya (W)", data: chartData.map(x=>x.value), borderColor:"#006b55", backgroundColor:"rgba(0,107,85,.12)", tension:0.35, fill:true, pointRadius:0, borderWidth:2 }]}, options:{ responsive:true, maintainAspectRatio:false, animation:false, plugins:{ legend:{display:false} }, scales:{ x:{ grid:{display:false}, ticks:{maxRotation:0, autoSkip:true} }, y:{ beginAtZero:true } } } }); } else { historyState.chart.data.labels = chartData.map(x=>x.label); historyState.chart.data.datasets[0].data = chartData.map(x=>x.value); historyState.chart.update(); } }
function loadHistory() { if (historyState.unsubscribe) return; const historyRef = query(ref(db, `readings/${DEVICE_ID}`), orderByKey(), limitToLast(500)); historyState.unsubscribe = onValue(historyRef, snap => { historyState.all = parseHistorySnapshot(snap); historyState.loaded = true; renderHistory(); }, () => { els.historyNotice.textContent = "Gagal mengambil data riwayat."; }); }
function exportHistoryCsv() { const data = historyState.filtered.length ? historyState.filtered : []; if (!data.length) return; const rows = ["timestamp,datetime,voltage,current,power,energy_kwh,frequency,power_factor"]; for (const r of data.slice().reverse()) rows.push([r.timestamp, `"${historyTimeFormat(r.timestamp, true)}"`, r.voltage ?? "", r.current ?? "", r.power ?? "", r.energy_kwh ?? "", r.frequency ?? "", r.power_factor ?? ""].join(",")); const blob = new Blob([rows.join("\n")], { type:"text/csv;charset=utf-8;" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `smart-energy-history-${new Date().toISOString().slice(0,10)}.csv`; a.click(); URL.revokeObjectURL(url); }

function validPredictionValue(value) { if (value === null || value === undefined || value === "") return null; const n = Number(value); return Number.isFinite(n) ? n : null; }
function fmtPredictionValue(value, digits, suffix = "") { const n = validPredictionValue(value); if (n === null) return "â€”"; return `${n.toFixed(digits)}${suffix}`; }
function fmtBool(value) { return value === true ? "Ya" : value === false ? "Tidak" : "â€”"; }
function fmtIso(value) { if (!value) return "â€”"; const d = new Date(value); if (Number.isNaN(d.getTime())) return String(value); return new Intl.DateTimeFormat("id-ID", { day:"2-digit", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit" }).format(d); }
function hoursFromNow(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return (Date.now() - d.getTime()) / 3_600_000;
}
function fmtClockAge(hours) {
  if (!Number.isFinite(hours)) return "â€”";
  if (hours < 0) return "sumber lebih baru dari jam perangkat";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} menit terhadap waktu sekarang`;
  if (hours < 48) return `${hours.toFixed(1)} jam terhadap waktu sekarang`;
  return `${(hours / 24).toFixed(1)} hari terhadap waktu sekarang`;
}
function isClockHistorical(data) {
  const sourceHours = hoursFromNow(data?.last_valid_raw_timestamp) ?? hoursFromNow(data?.prediction_feature_timestamp);
  return Number.isFinite(sourceHours) && sourceHours > 2;
}
function getPredictApiUrl() {
  const configured = window.SMART_ENERGY_PREDICT_API_URL;
  if (typeof configured === "string" && configured.trim()) {
    return configured.trim().replace(/\/$/, "") + "/api/predict";
  }
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    return "http://127.0.0.1:8000/api/predict";
  }
  return "/api/predict";
}
function hasPredictionPayload(data) {
  if (!data || typeof data !== "object") return false;
  const required = ["generated_at", "model_version", "prediction_status", "monthly_projection_status", "predicted_next_hour_kwh", "prediction_feature_timestamp", "prediction_target_timestamp", "projected_monthly_energy_kwh"];
  return required.every(key => data[key] !== null && data[key] !== undefined && data[key] !== "");
}
function resetPredictionUi() {
  els.predictionModelStatus.textContent = "Belum tersedia";
  els.predictionHeroLabel.textContent = "Prediksi";
  els.predictionHeroTitle.textContent = "Prediksi Belum Tersedia";
  els.predictionHeroSubtext.textContent = "Model atau hasil prediksi belum tersedia untuk ditampilkan.";
  els.predictionEnergyNextHour.textContent = "â€”";
  els.predictionTargetTimestamp.textContent = "â€”";
  els.predictionFeatureTimestamp.textContent = "â€”";
  els.predictionStaleness.textContent = "â€”";
  els.predictionModelVersion.textContent = "â€”";
  els.predictionRfUsed.textContent = "â€”";
  els.predictionMonthlyStatus.textContent = "â€”";
  els.predictionObservedEnergy.textContent = "â€”";
  els.predictionObservedCost.textContent = "â€”";
  els.predictionPastEstimate.textContent = "â€”";
  els.predictionRemainingEstimate.textContent = "â€”";
  els.predictionRemainingCost.textContent = "â€”";
  els.predictionMonthlyTotal.textContent = "â€”";
  els.predictionMonthlyCost.textContent = "â€”";
  els.predictionProjectionMethod.textContent = "â€”";
  els.predictionWarning.textContent = "";
  els.predictionWarning.classList.add("hidden");
  if (els.predictionCoverageWarning) els.predictionCoverageWarning.classList.add("hidden");
  els.predictionBaselineMae.textContent = "â€”";
  els.predictionBaselineRmse.textContent = "â€”";
  els.predictionBaselineR2.textContent = "â€”";
  els.predictionMae.textContent = "â€”";
  els.predictionRmse.textContent = "â€”";
  els.predictionR2.textContent = "â€”";
  els.predictionEvalHint.textContent = "Metrik evaluasi belum tersedia.";
  els.predictionMetricNote.textContent = "â€”";
  els.predictionResearchMinimum.textContent = "â€”";
  els.predictionFreshness.textContent = "â€”";
  els.predictionDataQuality.textContent = "â€”";
  if (els.predictionGeneratedAt) els.predictionGeneratedAt.textContent = "â€”";
  if (els.predictionSourceAge) els.predictionSourceAge.textContent = "â€”";
  if (els.predictionEnergyLabel) els.predictionEnergyLabel.textContent = "Prediksi Historis Terakhir";
}
function setPredictionState(data) {
  const hasData = hasPredictionPayload(data);
  predictionState.data = hasData ? data : null;
  predictionState.loaded = true;
  els.predictionEmptyState.classList.toggle("hidden", hasData);
  if (!hasData) { resetPredictionUi(); if (els.settingsModelStatus) els.settingsModelStatus.textContent = "Belum tersedia"; return; }

  const pipelineStale = data.prediction_fresh === false || data.prediction_status === "stale";
  const clockHistorical = isClockHistorical(data);
  const stale = pipelineStale || clockHistorical;
  els.predictionModelStatus.textContent = pipelineStale ? "Stale pipeline" : (clockHistorical ? "Data historis" : "Fresh");
  els.predictionModelStatus.classList.toggle("chip--warning", stale);
  els.predictionHeroLabel.textContent = "Prediksi";
  if (clockHistorical) {
    els.predictionHeroTitle.textContent = "Prediksi dari Data Historis";
    els.predictionHeroSubtext.textContent = "Sumber data lebih lama dari waktu sekarang. Hasil ini prediksi 1 jam setelah feature timestamp historis, bukan prediksi jam berjalan saat ini.";
  } else if (pipelineStale) {
    els.predictionHeroTitle.textContent = "Prediksi 1 Jam Belum Terbaru";
    els.predictionHeroSubtext.textContent = "Data fitur terakhir yang lengkap belum cukup untuk menghasilkan prediksi terkini.";
  } else {
    els.predictionHeroTitle.textContent = "Prediksi Konsumsi 1 Jam Berikutnya";
    els.predictionHeroSubtext.textContent = "Prediksi konsumsi energi untuk satu jam setelah feature timestamp terbaru.";
  }
  if (els.predictionEnergyLabel) {
    els.predictionEnergyLabel.textContent = (pipelineStale || clockHistorical) ? "Prediksi Historis Terakhir" : "Prediksi 1 Jam Berikutnya";
  }
  els.predictionEnergyNextHour.textContent = fmtPredictionValue(data.predicted_next_hour_kwh, 4, " kWh");
  els.predictionTargetTimestamp.textContent = fmtIso(data.prediction_target_timestamp);
  els.predictionFeatureTimestamp.textContent = fmtIso(data.prediction_feature_timestamp);
  els.predictionStaleness.textContent = fmtPredictionValue(data.prediction_staleness_hours, 2, " jam");
  if (els.predictionGeneratedAt) els.predictionGeneratedAt.textContent = fmtIso(data.generated_at);
  if (els.predictionSourceAge) {
    const sourceHours = hoursFromNow(data.last_valid_raw_timestamp) ?? hoursFromNow(data.prediction_feature_timestamp);
    els.predictionSourceAge.textContent = clockHistorical
      ? `Historis Â· ${fmtClockAge(sourceHours)}`
      : fmtClockAge(sourceHours);
  }
  els.predictionModelVersion.textContent = data.model_version ? String(data.model_version) : "â€”";
  els.predictionRfUsed.textContent = fmtBool(data.rf_used_in_monthly_projection);
  els.predictionMonthlyStatus.textContent = data.monthly_projection_status ? String(data.monthly_projection_status) : "â€”";
  const predUsageBefore = getUsageBeforeMonitoring();
  const predCurrentUsage = predUsageBefore + (validPredictionValue(data.observed_energy_kwh) ?? 0);
  const predProjectedTotal = predUsageBefore + (validPredictionValue(data.projected_monthly_energy_kwh) ?? 0);
  els.predictionObservedEnergy.textContent = fmtPredictionValue(data.observed_energy_kwh, 4, " kWh");
  els.predictionObservedCost.textContent = tieredCostLabel(predCurrentUsage);
  els.predictionPastEstimate.textContent = fmtPredictionValue(data.estimated_unobserved_past_energy_kwh, 4, " kWh");
  els.predictionRemainingEstimate.textContent = fmtPredictionValue(data.projected_remaining_energy_kwh, 4, " kWh");
  // Marginal cost: remaining cost = cost(projected_total) - cost(current_usage)
  els.predictionRemainingCost.textContent = (function() {
    const remaining = validPredictionValue(data.projected_remaining_energy_kwh);
    if (remaining === null) return "â€”";
    const diff = calculate450PostpaidEnergyCost(predProjectedTotal) - calculate450PostpaidEnergyCost(predCurrentUsage);
    return diff >= 0 ? fmtMoney(diff) : "â€”";
  })();
  els.predictionMonthlyTotal.textContent = fmtPredictionValue(data.projected_monthly_energy_kwh, 4, " kWh");
  els.predictionMonthlyCost.textContent = tieredCostLabel(predProjectedTotal);
  els.predictionProjectionMethod.textContent = clockHistorical
    ? "Hasil dihitung dari data sumber historis. Feature timestamp dan target timestamp merujuk ke jam data, bukan jam berjalan saat ini. Proyeksi bulanan mengikuti payload model; prediksi RF hanya masuk proyeksi jika prediction_fresh bernilai true."
    : stale
    ? "Proyeksi bulanan dihitung dari konsumsi aktual yang terobservasi dan rata-rata konsumsi per jam. Prediksi Random Forest hanya digunakan untuk satu jam berikutnya jika prediksi masih fresh. Pada kondisi saat ini, prediksi RF stale sehingga tidak digunakan dalam proyeksi bulan."
    : "Proyeksi bulanan dihitung dari konsumsi aktual yang terobservasi, rata-rata konsumsi per jam, dan prediksi Random Forest satu jam berikutnya jika prediksi masih fresh.";
  if (els.predictionCoverageWarning) els.predictionCoverageWarning.classList.toggle("hidden", data.coverage_from_month_start !== false);
  const warningParts = [];
  if (clockHistorical) warningParts.push("Sumber data historis terhadap waktu sekarang. Jangan baca hasil ini sebagai prediksi jam berjalan saat ini.");
  if (pipelineStale) warningParts.push("Prediksi RF stale terhadap pembacaan mentah terakhir dan tidak digunakan dalam proyeksi bulanan.");
  const warningText = warningParts.join(" ");
  els.predictionWarning.textContent = warningText;
  els.predictionWarning.classList.toggle("hidden", !warningText);

  const ev = data.evaluation || {};
  const baseline = ev.baseline || {};
  const rf = ev.random_forest || {};
  els.predictionBaselineMae.textContent = fmtPredictionValue(baseline.mae, 6);
  els.predictionBaselineRmse.textContent = fmtPredictionValue(baseline.rmse, 6);
  els.predictionBaselineR2.textContent = fmtPredictionValue(baseline.r2, 3);
  els.predictionMae.textContent = fmtPredictionValue(rf.mae, 6);
  els.predictionRmse.textContent = fmtPredictionValue(rf.rmse, 6);
  els.predictionR2.textContent = fmtPredictionValue(rf.r2, 3);
  const metricsAvailable = [baseline.mae, baseline.rmse, baseline.r2, rf.mae, rf.rmse, rf.r2].some(v => validPredictionValue(v) !== null);
  els.predictionEvalHint.textContent = metricsAvailable ? `${ev.train_rows ?? "â€”"} train / ${ev.test_rows ?? "â€”"} test` : "Metrik evaluasi belum tersedia.";
  els.predictionMetricNote.textContent = "Pada data pengujian kronologis, Random Forest belum mengungguli persistence baseline. Nilai MAE dan RMSE Random Forest lebih tinggi, sedangkan RÂ² lebih rendah dibandingkan baseline.";
  els.predictionResearchMinimum.textContent = data.research_minimum_met === true ? "Terpenuhi" : data.research_minimum_met === false ? "Belum terpenuhi" : "â€”";
  const freshnessBits = [data.prediction_status || "â€”"];
  if (clockHistorical) freshnessBits.push("sumber historis vs waktu sekarang");
  els.predictionFreshness.textContent = freshnessBits.join(" Â· ");
  els.predictionDataQuality.textContent = `Missing bucket: ${data.missing_hourly_bucket_count ?? "â€”"}; raw gap event: ${data.raw_reading_gap_event_count ?? "â€”"}`;
  if (els.settingsModelStatus) els.settingsModelStatus.textContent = hasData ? (stale ? "Model aktif, prediksi bukan jam berjalan" : "Model aktif") : "Belum tersedia";
}
function loadPrediction() {
  if (predictionState.unsubscribe) return;
  const predRef = ref(db, `predictions/${DEVICE_ID}/latest`);
  predictionState.unsubscribe = onValue(predRef, snap => {
    const val = snap.val();
    const incoming = val && Object.keys(val).length ? val : null;
    if (predictionState.liveGeneratedAt) {
      if (!incoming?.generated_at) return;
      const liveTs = Date.parse(predictionState.liveGeneratedAt);
      const incomingTs = Date.parse(incoming.generated_at);
      if (Number.isFinite(liveTs) && Number.isFinite(incomingTs) && incomingTs <= liveTs) return;
    }
    setPredictionState(incoming);
  }, () => {
    if (!predictionState.liveGeneratedAt) setPredictionState(null);
  });
}

function setPredictionRunStatus(message, kind) {
  if (!els.predictionRunStatus) return;
  els.predictionRunStatus.textContent = message;
  els.predictionRunStatus.classList.toggle("prediction-run-status--error", kind === "error");
  els.predictionRunStatus.classList.toggle("prediction-run-status--ok", kind === "ok");
}

function setPredictionRunLoading(isLoading) {
  if (!els.runPredictionBtn) return;
  els.runPredictionBtn.disabled = isLoading;
  els.runPredictionBtn.setAttribute("aria-busy", isLoading ? "true" : "false");
  if (els.runPredictionSpinner) els.runPredictionSpinner.classList.toggle("hidden", !isLoading);
  if (els.runPredictionBtnText) {
    els.runPredictionBtnText.textContent = isLoading ? "Menghitung..." : "Hitung Prediksi Random Forest";
  }
}

function predictErrorMessage(status, payload) {
  const detail = payload && typeof payload === "object" ? payload.detail : null;
  const detailText = typeof detail === "string" ? detail : "";
  if (status === 401) return "Sesi tidak valid atau kedaluwarsa. Masuk ulang, lalu coba lagi.";
  if (status === 422) return detailText || "Data riwayat belum cukup untuk prediksi.";
  if (status === 503) return "Layanan prediksi sedang tidak dapat memverifikasi sesi.";
  if (status === 0 || status === undefined) return "Tidak dapat terhubung ke layanan prediksi. Pastikan backend berjalan.";
  return "Perhitungan gagal. Coba lagi beberapa saat.";
}

async function runLivePrediction() {
  if (!els.runPredictionBtn || els.runPredictionBtn.disabled) return;
  const user = auth.currentUser;
  if (!user) {
    setPredictionRunStatus("Login diperlukan untuk menghitung prediksi.", "error");
    return;
  }
  setPredictionRunLoading(true);
  setPredictionRunStatus("Mengambil riwayat Firebase dan menjalankan inference RF-v1...", null);
  try {
    const token = await user.getIdToken();
    const response = await fetch(getPredictApiUrl(), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      setPredictionRunStatus(predictErrorMessage(response.status, payload), "error");
      return;
    }
    const prediction = payload && payload.prediction;
    if (!hasPredictionPayload(prediction)) {
      setPredictionRunStatus("Respons prediksi tidak lengkap.", "error");
      return;
    }
    predictionState.liveGeneratedAt = prediction.generated_at || new Date().toISOString();
    setPredictionState(prediction);
    const sourceHours = hoursFromNow(prediction.last_valid_raw_timestamp) ?? hoursFromNow(prediction.prediction_feature_timestamp);
    const historicalNote = isClockHistorical(prediction)
      ? ` Sumber data historis (${fmtClockAge(sourceHours)}).`
      : "";
    setPredictionRunStatus(`Perhitungan selesai. Model ${prediction.model_version || "RF-v1"}.${historicalNote}`, "ok");
  } catch {
    setPredictionRunStatus(predictErrorMessage(0), "error");
  } finally {
    setPredictionRunLoading(false);
  }
}

function setCommonTelemetry(data) {
  const voltage = Number(data.voltage ?? NaN);
  const current = Number(data.current ?? NaN);
  const power = Number(data.power ?? NaN);
  const energy = Number(data.energy_kwh ?? NaN);
  const frequency = Number(data.frequency ?? NaN);
  const pf = Number(data.power_factor ?? NaN);
  const ts = Number(data.timestamp ?? NaN);
  const isOnline = Number.isFinite(ts) && (Date.now() - ts) <= 30000;
  const timeLabel = Number.isFinite(ts)
    ? new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(ts))
    : 'Belum ada pembaruan';
  const agoLabel = Number.isFinite(ts) ? timeAgo(ts) : '--';
  return { voltage, current, power, energy, frequency, pf, ts, isOnline, timeLabel, agoLabel };
}

function setDeviceState(isOnline) {
  const text = isOnline ? "Online" : "Offline";
  els.deviceStatus.textContent = text;
  els.deviceStateLabel.textContent = text;
  els.connectionValue.textContent = text;
  if (els.monitorStatusText) els.monitorStatusText.textContent = text;
  if (els.settingsDeviceStatus) els.settingsDeviceStatus.textContent = text;
  els.statusDot.classList.toggle("status-dot--offline", !isOnline);
  els.statusDot.classList.toggle("status-dot--online", isOnline);
  if (els.monitorStatusDot) {
    els.monitorStatusDot.classList.toggle("status-dot--offline", !isOnline);
    els.monitorStatusDot.classList.toggle("status-dot--online", isOnline);
  }
}

function syncMonitoringState(t, label) {
  if (!els.monitorPowerValue) return;
  els.monitorLastUpdateText.textContent = label;
  els.monitorUpdatedAgo.textContent = t.agoLabel;
  els.monitorPowerValue.textContent = fmtNumber(t.power, 1);
  els.monitorVoltageValue.textContent = fmtNumber(t.voltage, 1);
  els.monitorCurrentValue.textContent = fmtNumber(t.current, 3);
  els.monitorPowerValueSmall.textContent = fmtNumber(t.power, 1);
  els.monitorEnergyValue.textContent = fmtNumber(t.energy, 4);
  els.monitorFrequencyValue.textContent = fmtNumber(t.frequency, 1);
  els.monitorPfValue.textContent = fmtNumber(t.pf, 2);
  setPowerGauge(els.monitorPowerGaugeFill, Number.isFinite(t.power) ? Math.max(0, Math.min(100, (t.power / 2500) * 100)) : 0);
  if (Number.isFinite(t.power)) updateMonitorChartPoint(label, t.power);
}

function setActivePage(page) {
  els.dashboardSection.classList.toggle('hidden', page !== 'dashboard');
  els.monitoringSection.classList.toggle('hidden', page !== 'monitoring');
  els.historySection.classList.toggle('hidden', page !== 'riwayat');
  els.predictionSection.classList.toggle('hidden', page !== 'prediksi');
  els.settingsSection.classList.toggle('hidden', page !== 'pengaturan');
  if (els.appTitle && els.appSubtitle) {
    if (page === 'pengaturan') {
      els.appTitle.textContent = 'Pengaturan';
      els.appSubtitle.textContent = 'Kelola preferensi Smart Energy Monitoring';
    } else if (page === 'prediksi') {
      els.appTitle.textContent = 'Prediksi';
      els.appSubtitle.textContent = 'Prediksi Konsumsi Energi Menggunakan Random Forest';
    } else if (page === 'riwayat') {
      els.appTitle.textContent = 'Riwayat';
      els.appSubtitle.textContent = 'Data historis konsumsi dan parameter listrik';
    } else if (page === 'monitoring') {
      els.appTitle.textContent = 'Monitoring';
      els.appSubtitle.textContent = 'Pemantauan Parameter Listrik Secara Real-time';
    } else {
      els.appTitle.textContent = 'Dashboard';
      els.appSubtitle.textContent = 'Monitoring Konsumsi Energi Listrik Berbasis IoT';
    }
  }
  els.navButtons.forEach(btn => { const active = btn.dataset.page === page; btn.classList.toggle('bottom-nav__item--active', active); btn.classList.toggle('desktop-nav__item--active', active); });
  if (page === 'pengaturan') syncSettingsUI();
}


function syncSettingsUI() {
  if (els.usageBeforeMonitoringInput) {
    const val = getUsageBeforeMonitoring();
    els.usageBeforeMonitoringInput.value = val > 0 ? String(val) : "";
  }
  if (els.pzemEnergyBaselineInput) {
    const baseline = getPzemEnergyBaseline();
    els.pzemEnergyBaselineInput.value = baseline > 0 ? String(baseline) : "";
  }
  if (els.settingsAccountEmail) els.settingsAccountEmail.textContent = auth.currentUser?.email || "--";
  if (els.settingsDeviceStatus) els.settingsDeviceStatus.textContent = latestState ? (Number.isFinite(Number(latestState.timestamp)) && (Date.now() - Number(latestState.timestamp) <= 30000) ? "ONLINE" : "OFFLINE") : "--";
  if (els.settingsModelStatus) els.settingsModelStatus.textContent = predictionState.data ? "Model aktif" : "Belum tersedia";
  if (els.settingsMsg) els.settingsMsg.textContent = "";
}
function saveUsageBefore() {
  const raw = els.usageBeforeMonitoringInput?.value?.trim();
  if (raw === "" || raw === undefined) {
    localStorage.removeItem("electricUsageBeforeMonitoring");
    els.settingsMsg.textContent = "Pemakaian sebelum monitoring direset ke 0.";
  } else {
    const val = Number(raw);
    if (!Number.isFinite(val) || val < 0) {
      els.settingsMsg.textContent = "Masukkan angka >= 0.";
      return;
    }
    localStorage.setItem("electricUsageBeforeMonitoring", String(val));
    els.settingsMsg.textContent = "Pemakaian sebelum monitoring berhasil disimpan.";
  }
  refreshLocalDerivedViews();
}
function savePzemBaseline() {
  const raw = els.pzemEnergyBaselineInput?.value?.trim();
  if (raw === "" || raw === undefined) {
    localStorage.removeItem("pzemEnergyBaseline");
    els.settingsMsg.textContent = "Baseline PZEM direset ke 0.";
  } else {
    const val = Number(raw);
    if (!Number.isFinite(val) || val < 0) {
      els.settingsMsg.textContent = "Baseline PZEM harus angka >= 0.";
      return;
    }
    localStorage.setItem("pzemEnergyBaseline", String(val));
    els.settingsMsg.textContent = "Baseline PZEM berhasil disimpan.";
  }
  refreshLocalDerivedViews();
}
function useCurrentPzemEnergy() {
  const raw = latestState ? Number(latestState.energy_kwh) : NaN;
  if (!Number.isFinite(raw)) {
    els.settingsMsg.textContent = "Data energi PZEM belum tersedia.";
    return;
  }
  if (els.pzemEnergyBaselineInput) els.pzemEnergyBaselineInput.value = raw.toFixed(4);
  els.settingsMsg.textContent = "Nilai PZEM saat ini dimasukkan. Tekan Simpan Baseline PZEM untuk menyimpan.";
}
function resetPzemBaseline() {
  localStorage.removeItem("pzemEnergyBaseline");
  if (els.pzemEnergyBaselineInput) els.pzemEnergyBaselineInput.value = "";
  if (els.settingsMsg) els.settingsMsg.textContent = "Baseline PZEM berhasil direset.";
  refreshLocalDerivedViews();
}
function saveTariff() {
  // tariff profile is fixed 450VA; this is kept for potential future override
  els.settingsMsg.textContent = "Profil tarif 450 VA Pascabayar aktif.";
}
function resetTariff() {
  if (!window.confirm("Reset pemakaian sebelum monitoring?")) return;
  localStorage.removeItem("electricUsageBeforeMonitoring");
  if (els.usageBeforeMonitoringInput) els.usageBeforeMonitoringInput.value = "";
  if (els.settingsMsg) els.settingsMsg.textContent = "Pemakaian sebelum monitoring berhasil direset.";
  refreshLocalDerivedViews();
}

function renderState(data) {
  if (!data) return;
  latestState = data;
  const t = setCommonTelemetry(data);

  els.voltageValue.textContent = fmtNumber(t.voltage, 1);
  els.currentValue.textContent = fmtNumber(t.current, 3);
  els.powerValue.textContent = fmtNumber(t.power, 1);
  els.powerValueSmall.textContent = fmtNumber(t.power, 1);
  els.energyValue.textContent = fmtNumber(t.energy, 4);
  els.energyValueSmall.textContent = fmtNumber(t.energy, 4);
  els.frequencyValue.textContent = fmtNumber(t.frequency, 1);
  els.pfValue.textContent = fmtNumber(t.pf, 2);
  els.lastUpdateText.textContent = t.timeLabel;
  els.updatedAgo.textContent = t.agoLabel;
  const usageBefore = getUsageBeforeMonitoring();
  const pzemBaseline = getPzemEnergyBaseline();
  const monitored = calculateMonitoredEnergy(t.energy, pzemBaseline);
  const monitoredEnergy = monitored.monitored ?? 0;
  const monthlyUsage = usageBefore + monitoredEnergy;
  const biayaBeban = TARIFF_PROFILE.daya_kva * TARIFF_PROFILE.biaya_beban_per_kva;
  const energyCost = calculate450PostpaidEnergyCost(monthlyUsage);
  els.tariffValue.textContent = TARIFF_PROFILE.name;
  if (els.tariffDetail) els.tariffDetail.textContent = `Tarif bertingkat â€¢ ${TARIFF_PROFILE.code}`;
  els.costValue.textContent = Number.isFinite(t.energy) ? fmtMoney(energyCost) : "--";
  if (els.costBreakdown) {
    let breakdown = `Pemakaian bulan: ${monthlyUsage.toFixed(4)} kWh`;
    if (pzemBaseline > 0 && Number.isFinite(t.energy)) breakdown += `\nPZEM kumulatif: ${t.energy.toFixed(4)} kWh Â· Baseline PZEM: ${pzemBaseline.toFixed(4)} kWh\nTercatat instalasi ini: ${monitoredEnergy.toFixed(4)} kWh`;
    else if (Number.isFinite(t.energy)) breakdown += `\nTercatat PZEM: ${t.energy.toFixed(4)} kWh`;
    if (usageBefore > 0) breakdown += `\nSebelum monitoring: ${usageBefore.toFixed(4)} kWh`;
    els.costBreakdown.textContent = breakdown;
  }
  if (els.pzemBaselineWarning) {
    els.pzemBaselineWarning.textContent = monitored.reset ? "Nilai energi PZEM saat ini lebih kecil dari baseline. Kemungkinan meter PZEM telah di-reset. Periksa baseline di Pengaturan." : "";
    els.pzemBaselineWarning.classList.toggle("hidden", !monitored.reset);
  }
  if (els.loadCostValue) els.loadCostValue.textContent = fmtMoney(biayaBeban);
  setDeviceState(t.isOnline);
  setPowerGauge(els.powerGaugeFill, Number.isFinite(t.power) ? Math.max(0, Math.min(100, (t.power / 2500) * 100)) : 0);

  const label = Number.isFinite(t.ts) ? new Date(t.ts).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : new Date().toLocaleTimeString("id-ID");
  if (Number.isFinite(t.power)) updateChartPoint(label, t.power);
  syncMonitoringState(t, label);
}

function attachRealtime() {
  if (latestUnsubscribe) latestUnsubscribe();
  const dataRef = ref(db, devicePath);
  latestUnsubscribe = onValue(dataRef, snap => {
    const val = snap.val();
    if (val) renderState(val);
  }, () => {
    els.loginMsg.textContent = "Gagal mengambil data monitoring.";
  });
}

els.loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  setLoginError("");
  setLoading(true);
  try {
    await signInWithEmailAndPassword(auth, els.email.value.trim(), els.password.value);
  } catch (err) {
    setLoginError("Login gagal. Periksa email dan password.");
  } finally {
    setLoading(false);
  }
});

els.togglePasswordBtn.addEventListener("click", () => {
  const hidden = els.password.type === "password";
  els.password.type = hidden ? "text" : "password";
  els.togglePasswordBtn.innerHTML = `<span class="material-symbols-outlined">${hidden ? "visibility_off" : "visibility"}</span>`;
  els.togglePasswordBtn.setAttribute("aria-label", hidden ? "Sembunyikan password" : "Tampilkan password");
});

els.logoutBtn.addEventListener("click", () => signOut(auth));
els.settingsLogoutBtn?.addEventListener("click", () => signOut(auth));
els.saveTariffBtn?.addEventListener("click", saveTariff);
els.saveUsageBeforeBtn?.addEventListener("click", saveUsageBefore);
els.savePzemBaselineBtn?.addEventListener("click", savePzemBaseline);
els.useCurrentPzemBtn?.addEventListener("click", useCurrentPzemEnergy);
els.resetPzemBaselineBtn?.addEventListener("click", resetPzemBaseline);
els.resetTariffBtn?.addEventListener("click", resetTariff);
els.navButtons.forEach(btn => btn.addEventListener("click", () => setActivePage(btn.dataset.page)));
els.historyRangeFilter?.addEventListener("click", (e) => { const btn = e.target.closest("button[data-range]"); if (!btn) return; historyState.filter = btn.dataset.range; els.historyRangeFilter.querySelectorAll(".segmented__item").forEach(x => x.classList.toggle("segmented__item--active", x === btn)); renderHistory(); });
els.exportCsvBtn?.addEventListener("click", exportHistoryCsv);
els.runPredictionBtn?.addEventListener("click", () => { runLivePrediction(); });


onAuthStateChanged(auth, (user) => {
  els.authLoading.classList.add("hidden");
  if (user) {
    els.loginView.classList.add("hidden");
    els.appView.classList.remove("hidden");
    initGauge();
    initMonitorGauge();
    attachRealtime();
    loadHistory();
    loadPrediction();
    syncSettingsUI();
    setActivePage('dashboard');
  } else {
    els.appView.classList.add("hidden");
    els.loginView.classList.remove("hidden");
    if (latestUnsubscribe) {
      latestUnsubscribe();
      latestUnsubscribe = null;
    }
  }
});

