# Random Forest Local Training

Tujuan:
- Ekspor history nyata Firebase ke CSV lokal.
- Bangun pipeline training Random Forest dari data history nyata.
- Input utama: CSV history ekspor dari `readings/esp32-01`.
- `energy_kwh` pada PZEM adalah cumulative meter, bukan jumlah interval.

## Export history nyata
Script:
- `ml/export_firebase_history.py`

Cara pakai:
```bash
python ml/export_firebase_history.py
```

Saat jalan, script akan minta:
- Firebase email
- Firebase password

Password tidak tampil saat diketik.

Export akan simpan:
- `ml/data/history_real.csv`

## Format input training
CSV dengan kolom minimal:
- `timestamp`
- `voltage`
- `current`
- `power`
- `energy_kwh`
- `frequency`
- `power_factor`

## Install dependency
```bash
pip install -r requirements.txt
```

## Jalankan training
```bash
python train_random_forest.py --input ml/data/history_real.csv --output ml/output
```

## Pipeline
- Parse `timestamp` ke datetime UTC lalu konversi ke `Asia/Jakarta`
- Sort ascending
- Drop row invalid / duplicate timestamp
- Hitung `meter_delta = energy_kwh(current) - energy_kwh(previous)`
- Delta negatif dianggap reset / invalid
- Delta valid dijumlahkan per jam menjadi `energy_kwh_hourly`
- Buat timeline jam kontinu dengan `reindex`
- Jam hilang tetap NaN, tidak diisi 0
- Flag coverage buruk / gap besar per jam
- Buat fitur:
  - `voltage_mean`
  - `current_mean`
  - `power_mean`
  - `frequency_mean`
  - `power_factor_mean`
  - `hour_of_day`
  - `day_of_week`
  - `energy_current_hour_kwh`
  - `energy_lag_1h`
  - `energy_lag_24h`
- Target:
  - `energy_next_hour_kwh`

## Split
- Chronological split 80% train, 20% test
- Tidak shuffle

## Baseline
Persistence baseline:
- prediksi next hour = konsumsi jam saat ini
- secara runtime: `y_pred = energy_current_hour_kwh(t)`
- target tetap `energy_next_hour_kwh(t)`

## Output
Jika training cukup data:
- `ml/output/random_forest_model.joblib`
- `ml/output/metrics.json`
- `ml/output/feature_importance.csv`

Jika data belum cukup:
- pipeline preprocessing tetap jalan
- training tidak dilakukan
- tidak simpan model palsu

## Catatan
- `energy_kwh` pada PZEM adalah cumulative meter
- konsumsi dibuat dari delta reading berturut-turut, bukan penjumlahan cumulative
- meter reset / delta negatif ditolak
- timeline jam dibuat kontinu supaya shift 1/24 benar-benar berarti 1/24 jam
- jam hilang tetap NaN, bukan 0
- jam dengan coverage buruk dapat dikeluarkan dari training
- Script tidak menulis ke Firebase
- Script tidak mengubah frontend
- Script tidak membuat data dummy
