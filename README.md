# Smart Home Energy Monitoring - ESP32, IoT & Random Forest

Repository implementasi penelitian skripsi:

> **Pengembangan Monitoring Smart Home Energy Berbasis ESP32 dengan Internet of Things Menggunakan Algoritma Random Forest untuk Efisiensi Konsumsi Energi Listrik**

**Author:** Muhammad Adilaga  
**Program Studi:** Teknik Informatika  
**Tahun:** 2026

---

## Tentang Project

Project ini mengembangkan sistem monitoring konsumsi energi listrik rumah tangga yang mengintegrasikan perangkat keras monitoring, Internet of Things (IoT), Firebase Realtime Database, dashboard web, dan machine learning.

PZEM-004T-100A V4.0 digunakan untuk membaca enam parameter kelistrikan:

| Parameter | Satuan |
|---|---|
| Tegangan | V |
| Arus | A |
| Daya aktif | W |
| Energi | kWh |
| Frekuensi | Hz |
| Faktor daya | - |

Data dibaca oleh ESP32 melalui komunikasi UART dan ditampilkan secara lokal menggunakan LCD I2C 16x2.

Ketika koneksi Wi-Fi tersedia, data dikirim ke Firebase Realtime Database untuk monitoring real-time, penyimpanan historis, visualisasi dashboard, dan pembentukan dataset machine learning.

Monitoring lokal tetap berjalan ketika koneksi internet terputus.

---

## Arsitektur Sistem

```text
PZEM-004T V4
      |
      v
    ESP32
      |
      +------------------> LCD I2C
      |                   Monitoring lokal
      |
      +---- Wi-Fi -------> Firebase Realtime Database
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
          Dashboard Web               Historical Data
                                             |
                                             v
                                      Preprocessing
                                             |
                                             v
                                  Random Forest Regression
                                             |
                                             v
                               Prediksi konsumsi 1 jam
                                             |
                                             v
                                Proyeksi akhir bulan
                                             |
                                             v
                                      Dashboard Web
```

---

## Firebase Data Structure

Sistem memisahkan data berdasarkan fungsi:

| Firebase Path | Fungsi |
|---|---|
| `devices/esp32-01/latest` | Pembacaan terbaru untuk monitoring real-time |
| `readings/esp32-01` | Data historis bertimestamp |
| `predictions/esp32-01/latest` | Hasil prediksi terbaru |

Dashboard menggunakan Firebase Authentication sebelum pengguna dapat membaca data monitoring.

---

## Dashboard Web

Dashboard dikembangkan menggunakan HTML, CSS, dan JavaScript.

Antarmuka menyediakan halaman:

- Login
- Dashboard
- Monitoring
- Riwayat
- Prediksi
- Pengaturan

Untuk menjalankan dashboard secara lokal:

```powershell
python -m http.server 8000 -d public
```

Kemudian buka:

```text
http://localhost:8000
```

Login menggunakan akun yang telah terdaftar pada Firebase Authentication.

---

## Random Forest Regression

Machine learning digunakan untuk memprediksi konsumsi energi pada satu jam berikutnya berdasarkan data historis sistem monitoring.

Target model:

```text
energy_next_hour_kwh
```

Feature utama yang digunakan:

| Feature | Keterangan |
|---|---|
| `voltage_mean` | Rata-rata tegangan per jam |
| `current_mean` | Rata-rata arus per jam |
| `power_mean` | Rata-rata daya per jam |
| `frequency_mean` | Rata-rata frekuensi |
| `power_factor_mean` | Rata-rata faktor daya |
| `hour_of_day` | Jam dalam satu hari |
| `day_of_week` | Hari dalam minggu |
| `energy_current_hour_kwh` | Konsumsi energi jam saat ini |
| `energy_lag_1h` | Konsumsi satu jam sebelumnya |
| `energy_lag_24h` | Konsumsi 24 jam sebelumnya |

Data energi dari PZEM bersifat kumulatif sehingga konsumsi interval tidak diperoleh dengan menjumlahkan nilai meter.

Konsumsi energi dihitung dari delta nilai energi kumulatif yang berurutan, kemudian diagregasikan menjadi interval satu jam.

---

## Training dan Evaluation

Dataset dibagi secara kronologis:

```text
80% periode awal  -> Training
20% periode akhir -> Testing
```

Data tidak diacak karena penelitian menggunakan data time series.

Model dievaluasi menggunakan:

- Mean Absolute Error (MAE)
- Root Mean Squared Error (RMSE)
- R-squared (R²)

Selain Random Forest, digunakan **persistence baseline**, yaitu konsumsi energi jam saat ini digunakan sebagai prediksi konsumsi pada satu jam berikutnya.

Baseline digunakan untuk mengetahui apakah Random Forest memberikan peningkatan dibandingkan pendekatan prediksi sederhana.

---

## Current Experimental Status

Snapshot dataset terbaru yang telah diekspor dari Firebase:

```text
Raw readings        : 8,803
Coverage            : ~223.67 jam
Distinct data hours : 155
Valid hourly slots  : 143
Training rows       : 76
Testing rows        : 20
```

Model Random Forest telah berhasil dilatih menggunakan dataset terbaru.

Hasil evaluasi saat ini:

| Model | MAE (kWh) | RMSE (kWh) | R² |
|---|---:|---:|---:|
| Persistence Baseline | 0.00520 | 0.01022 | 0.11094 |
| Random Forest | 0.00653 | 0.01090 | -0.01205 |

Pada eksperimen saat ini, Random Forest belum mengungguli persistence baseline pada data pengujian.

Hasil tersebut tetap dipertahankan sebagai hasil penelitian dan menjadi dasar analisis lebih lanjut mengenai kontinuitas dataset, variasi pola beban, feature engineering, serta kecukupan data.

---

## Prediction Pipeline

Pipeline machine learning yang digunakan:

```text
Firebase History
      |
      v
Export Dataset
      |
      v
Dataset Audit
      |
      v
Hourly Preprocessing
      |
      v
Feature Engineering
      |
      v
Random Forest Training
      |
      v
Model Evaluation
      |
      v
Generate Prediction
      |
      v
Freshness Validation
      |
      v
Firebase Prediction
```

Prediction tidak boleh dipublish ke Firebase apabila hasil prediksi sudah stale.

Script publish melakukan validasi terhadap:

```text
prediction_status == "fresh"
prediction_fresh == true
prediction_staleness_hours <= 1
```

Dengan mekanisme tersebut, hasil prediksi yang sudah terlalu lama tidak akan dipublish sebagai prediction terbaru.

---

## ML Workflow

Urutan workflow machine learning:

### 1. Export data dari Firebase

```powershell
python .\ml\export_firebase_history.py
```

### 2. Audit dataset

```powershell
python .\ml\_audit_hourly.py
```

### 3. Training Random Forest

```powershell
python .\ml\train_random_forest.py --input .\ml\data\history_real.csv
```

### 4. Generate prediction

```powershell
python .\ml\predict_energy.py
```

### 5. Publish prediction

```powershell
python .\ml\publish_prediction.py
```

Prediction harus memiliki status `fresh` sebelum dapat dipublish.

---

## ML Scripts

| File | Fungsi |
|---|---|
| `ml/export_firebase_history.py` | Export historical Firebase data ke CSV |
| `ml/_audit_hourly.py` | Audit kontinuitas dan kualitas dataset |
| `ml/train_random_forest.py` | Preprocessing dan training Random Forest |
| `ml/predict_energy.py` | Membuat prediksi terbaru |
| `ml/publish_prediction.py` | Validasi dan publish prediction ke Firebase |
| `ml/requirements.txt` | Dependency Python |

Generated dataset dan model tidak disimpan ke Git repository.

Folder dan file hasil proses machine learning di-ignore melalui `.gitignore`, termasuk:

```text
.venv/
ml/data/*.csv
ml/output/*
```

File berikut tetap disimpan:

```text
ml/output/.gitkeep
```

Tujuannya agar struktur direktori `ml/output` tetap tersedia setelah repository di-clone.

---

## Project Structure

```text
smart-energy-firebase-complete/
|
|-- .gitignore
|-- firebase.json
|-- README.md
|
|-- public/
|   |-- index.html
|   |-- app.js
|   |-- style.css
|   `-- firebase-config.js
|
`-- ml/
    |-- README.md
    |-- export_firebase_history.py
    |-- _audit_hourly.py
    |-- train_random_forest.py
    |-- predict_energy.py
    |-- publish_prediction.py
    |-- requirements.txt
    |
    |-- data/
    |
    `-- output/
        `-- .gitkeep
```

---

## Python Environment

Buat virtual environment:

```powershell
python -m venv .venv
```

Aktifkan environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependency:

```powershell
pip install -r .\ml\requirements.txt
```

---

## Security

Firebase web configuration merupakan konfigurasi client-side dan bukan pengganti mekanisme keamanan.

Keamanan akses tetap harus diterapkan melalui Firebase Authentication dan Firebase Realtime Database Security Rules.

Credential sensitif seperti password, service account, file `.env`, dan secret lainnya tidak boleh disimpan di repository.

---

## Research Scope

Repository ini merupakan implementasi perangkat lunak dari penelitian skripsi dan bukan sistem kontrol otomatis beban listrik.

Random Forest digunakan untuk prediksi konsumsi energi dan tidak digunakan untuk melakukan pemutusan atau pengendalian otomatis terhadap beban PLN.

Estimasi biaya, apabila ditampilkan pada dashboard, merupakan fitur informatif berdasarkan konsumsi kWh dan tarif yang dimasukkan pengguna.

Nilai biaya bukan target Random Forest.

---

## Electrical Safety

Project berinteraksi dengan sistem listrik AC.

Instalasi PZEM-004T dan current transformer harus dilakukan dengan mengikuti prosedur keselamatan kelistrikan.

Jangan melakukan pemasangan, perubahan wiring, atau menyentuh konduktor ketika sumber PLN masih aktif.

---

## Research Status

**Development / Undergraduate Thesis Research - 2026**

Sistem monitoring, penyimpanan data historis, dashboard, pipeline machine learning, training Random Forest, prediction generation, freshness validation, dan publishing prediction telah berhasil diimplementasikan.

Pengumpulan data dan evaluasi masih dapat dilanjutkan untuk memperoleh dataset yang lebih panjang dan kontinu serta mengevaluasi peningkatan performa model.

---

## Usage

Repository ini dibuat untuk keperluan penelitian akademik dan pengembangan sistem Smart Home Energy Monitoring.

Belum ada lisensi open-source yang ditetapkan untuk repository ini.