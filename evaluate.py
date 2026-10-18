"""Evaluate IoT Lab 2 CSV quality and optional ThingsBoard sample age.
Run: python evaluate.py [--online]. No InfluxDB writes.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
SENSORS = ("temperature", "humidity", "distance_cm")


def read_export_csv(path):
    """Read SQL wide CSV or InfluxDB annotated Flux CSV (including table blocks)."""
    from io import StringIO

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        lines = file.readlines()
    if not lines:
        raise ValueError("{}: CSV is empty".format(path.name))

    first = next((line.strip() for line in lines if line.strip()), "")
    if first.startswith("#group") or first.startswith(",#group"):
        blocks = []
        current = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith(",#"):
                if current:
                    blocks.append(current)
                    current = []
                continue
            if current and (stripped.startswith(",result,") or
                            stripped.startswith("result,table,")):
                blocks.append(current)
                current = []
            current.append(line)
        if current:
            blocks.append(current)
        frames = []
        for block in blocks:
            frame = pd.read_csv(StringIO("".join(block)))
            frame.columns = frame.columns.astype(str).str.strip()
            if "_time" in frame.columns or "time" in frame.columns:
                frames.append(frame)
        if not frames:
            raise ValueError("{}: no time field in Flux CSV blocks".format(path.name))
        df = pd.concat(frames, ignore_index=True, sort=False)
    else:
        df = pd.read_csv(str(path), encoding="utf-8-sig")
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~df.columns.str.startswith("Unnamed:")]
    df = df.rename(columns={"_time": "time"})

    # InfluxDB Flux often exports one row per (timestamp, sensor), not a wide table.
    if "_field" in df.columns and "_value" in df.columns:
        df = df[df["_field"].isin(SENSORS)].copy()
        if "time" not in df.columns:
            raise ValueError("{}: Flux long CSV has no timestamp".format(path.name))
        df["_value"] = pd.to_numeric(df["_value"], errors="coerce")
        keys = ["time"]
        if "device_id" in df.columns:
            keys.append("device_id")
        df = df.pivot_table(index=keys, columns="_field", values="_value",
                            aggfunc="mean", dropna=False).reset_index()
        df.columns.name = None

    if "time" not in df.columns:
        raise ValueError("{}: missing time column. Available columns: {}. "
                         "Please send the first 6 CSV lines (without secrets)."
                         .format(path.name, list(df.columns)))
    return df


def describe(path):
    if not path.is_file():
        return {"status": "not_found", "filename": path.name}
    df = read_export_csv(path)
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    times = df["time"].dropna()
    result = {
        "status": "ok", "filename": path.name, "rows": int(len(df)),
        "invalid_timestamp_rows": int(df["time"].isna().sum()),
        "duplicate_timestamp_rows": int(times.duplicated().sum()),
        "start_utc": times.min().isoformat() if not times.empty else None,
        "end_utc": times.max().isoformat() if not times.empty else None,
        "sensor_stats": {},
    }
    if len(times) > 1:
        unique_times = times.drop_duplicates().sort_values()
        gaps = unique_times.diff().dt.total_seconds().dropna()
        result["duration_minutes"] = round((times.max() - times.min()).total_seconds()/60, 2)
        result["largest_gap_seconds"] = round(float(gaps.max()), 2) if not gaps.empty else None
    for name in SENSORS:
        if name not in df.columns:
            result["sensor_stats"][name] = {"status": "missing_column"}
            continue
        values = pd.to_numeric(df[name], errors="coerce")
        available = values.dropna()
        stats = {
            "non_null": int(values.notna().sum()), "missing": int(values.isna().sum()),
            "missing_percent": round(100 * float(values.isna().mean()), 2) if len(df) else None,
            "min": float(available.min()) if not available.empty else None,
            "max": float(available.max()) if not available.empty else None,
            "mean": round(float(available.mean()), 3) if not available.empty else None,
        }
        flag = name + "_outlier"
        if flag in df.columns:
            stats["outliers_flagged"] = int(pd.to_numeric(df[flag], errors="coerce").fillna(0).sum())
        result["sensor_stats"][name] = stats
    return result


def thingsboard_freshness():
    """This measures HTTP RTT and sample age, NOT end-to-end pipeline latency."""
    import requests
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
    url = os.getenv("TB_URL", "").rstrip("/")
    token = os.getenv("TB_API_KEY", "")
    device = os.getenv("TB_DEVICE_ID", "")
    if not all((url, token, device)):
        return {"status": "not_configured"}
    endpoint = "{}/api/plugins/telemetry/DEVICE/{}/values/timeseries".format(url, device)
    start = time.time()
    resp = requests.get(endpoint, headers={"X-Authorization": "ApiKey " + token},
                        params={"keys": ",".join(SENSORS)}, timeout=15)
    resp.raise_for_status()
    finish = time.time()
    ages = {}
    for name, items in resp.json().items():
        if name in SENSORS and items:
            ages[name] = round(finish - max(int(item["ts"]) for item in items)/1000.0, 3)
    return {"status": "ok", "http_round_trip_seconds": round(finish-start, 3),
            "latest_sample_age_seconds": ages,
            "note": "Sample age is NOT MQTT-to-InfluxDB or end-to-end latency."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    result = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "raw": describe(BASE/"sensor_raw.csv"),
              "processed": describe(BASE/"processed_data.csv")}
    if args.online:
        try:
            result["thingsboard"] = thingsboard_freshness()
        except Exception as exc:
            result["thingsboard"] = {"status": "error", "message": str(exc)}
    destination = BASE/"evaluation_report.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Saved:", destination.name)


if __name__ == "__main__":
    main()
