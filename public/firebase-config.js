export const firebaseConfig = {
  apiKey: "AIzaSyCVgIVHs5ZP-YBTgUVRoclkD674gJSFeN8",
  authDomain: "smart-energy-monitoring-1e14f.firebaseapp.com",
  databaseURL: "https://smart-energy-monitoring-1e14f-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "smart-energy-monitoring-1e14f",
  storageBucket: "smart-energy-monitoring-1e14f.firebasestorage.app",
  messagingSenderId: "856196767584",
  appId: "1:856196767584:web:5aa42cb73e1416e4118805"
};

export const DEVICE_ID = "esp32-01";

export const PREDICT_API_BASE_URL = "https://smart-energy-firebase-complete-production.up.railway.app";

/**
 * Location allowlist: { code: label }
 * Machine-readable code stored in Firebase records.
 * Human-readable label displayed in UI.
 */
export const LOCATION_ALLOWLIST = {
  ruang_kerja: "Ruang Kerja",
  kamar_tidur: "Kamar Tidur",
  ruang_tamu: "Ruang Tamu",
  dapur: "Dapur",
};

export const LOCATION_UNKNOWN_LABEL = "Lokasi tidak diketahui";
