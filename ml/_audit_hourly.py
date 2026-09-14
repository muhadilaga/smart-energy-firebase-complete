from pathlib import Path
import pandas as pd
import json

path = Path(r'D:/Dev/Projects/smart-energy-firebase-complete/ml/data/history_real.csv')
df = pd.read_csv(path)
raw_rows = len(df)
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True, errors='coerce').dt.tz_convert('Asia/Jakarta')
for c in ['voltage','current','power','energy_kwh','frequency','power_factor']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df = df.dropna(subset=['timestamp']).sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='last').reset_index(drop=True)
df['hour'] = df['timestamp'].dt.floor('h')
df['reading_gap_seconds'] = df['timestamp'].diff().dt.total_seconds()
df['meter_delta'] = df['energy_kwh'].diff()
df['meter_reset_flag'] = df['meter_delta'].lt(0)
df['meter_delta_valid'] = df['meter_delta'].where((df['meter_delta'].notna()) & (df['meter_delta'] >= 0))

rows=[]
for hour, g in df.groupby('hour', sort=True):
    g = g.sort_values('timestamp')
    rows.append({
        'hour': hour,
        'reading_count': int(len(g)),
        'first_reading': g['timestamp'].iloc[0],
        'last_reading': g['timestamp'].iloc[-1],
        'max_gap_seconds': float(g['reading_gap_seconds'].max()) if g['reading_gap_seconds'].notna().any() else None,
        'meter_reset_count': int(g['meter_reset_flag'].fillna(False).sum()),
        'energy_kwh_hourly': float(g['meter_delta_valid'].sum()) if g['meter_delta_valid'].notna().any() else None,
    })
obs = pd.DataFrame(rows)
obs['coverage_flag'] = (obs['max_gap_seconds'].fillna(0) > 180) | (obs['reading_count'] < 2) | (obs['meter_reset_count'] > 0)

start = df['hour'].min()
end = df['hour'].max()
full = pd.date_range(start=start, end=end, freq='h', tz='Asia/Jakarta')
full_set = set(full)
missing_slots = [h for h in full if h not in set(df['hour'])]
reading_gap_event_count = int((df['reading_gap_seconds'] > 180).sum())
hours_with_gap = sorted(df.loc[df['reading_gap_seconds'] > 180, 'hour'].astype(str).unique().tolist())

print(json.dumps({
    'raw_reading_count': raw_rows,
    'observed_distinct_hours': len(obs),
    'continuous_timeline_hours': len(full),
    'missing_hour_slots': len(missing_slots),
    'reading_gap_event_count_gt_180s': reading_gap_event_count,
    'hour_with_gap_count': len(hours_with_gap),
    'max_gap_seconds': float(df['reading_gap_seconds'].max()) if df['reading_gap_seconds'].notna().any() else None,
    'coverage_flagged_hours': int(obs['coverage_flag'].sum()),
    'valid_hour_slots': int((~obs['coverage_flag']).sum()),
}, ensure_ascii=False, indent=2))
print('OBSERVED HOURS TABLE')
for _, r in obs.iterrows():
    print(f"{r['hour']:%Y-%m-%d %H:%M %z} | {int(r['reading_count'])} | {r['first_reading'].isoformat()} | {r['last_reading'].isoformat()} | {r['max_gap_seconds']} | {int(r['meter_reset_count'])} | {r['energy_kwh_hourly']} | {bool(r['coverage_flag'])}")
print('PARTIAL HOUR AUDIT')
for _, r in obs.iterrows():
    print(f"{r['hour']:%Y-%m-%d %H:%M %z} | reading_count={int(r['reading_count'])} | first={r['first_reading']:%H:%M} | last={r['last_reading']:%H:%M} | max_gap={r['max_gap_seconds']} | reset={int(r['meter_reset_count'])} | coverage_flag={bool(r['coverage_flag'])}")
print('VALID HOURLY HOURS')
for _, r in obs.loc[~obs['coverage_flag']].iterrows():
    print(r['hour'].isoformat())
