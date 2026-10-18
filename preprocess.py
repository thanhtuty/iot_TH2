"""IoT Lab 2: CSV export from InfluxDB Cloud Serverless -> preprocess -> InfluxDB.
Compatible with Python 3.8 (subject to installed pandas/numpy/influxdb-client).
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

URL = os.environ["INFLUX_URL"].rstrip("/")
TOKEN = os.environ["INFLUX_TOKEN"]
ORG = os.environ["INFLUX_ORG"]
BUCKET = os.environ["INFLUX_BUCKET"]
DEVICE = os.environ["TB_DEVICE_ID"]
SENSORS = ["temperature", "humidity", "distance_cm"]
INPUT_CSV = BASE_DIR / "sensor_raw.csv"
OUTPUT_CSV = BASE_DIR / "processed_data.csv"


def read_data():
"""Read InfluxDB exported CSV: annotated Flux long format or SQL wide CSV."""
if not INPUT_CSV.exists():
    raise FileNotFoundError("Khong tim thay sensor_raw.csv trong thu muc IoT_Lab2")

with open(str(INPUT_CSV), "r", encoding="utf-8-sig", newline="") as f:
    first = f.readline().lstrip("\ufeff").strip()

if first.startswith("#group") or first.startswith(",#group"):
    # Flux annotated CSV may contain multiple blocks, each with its own
    # #group/#datatype/#default metadata and a header row.
    import csv
    from io import StringIO

    with open(str(INPUT_CSV), "r", encoding="utf-8-sig", newline="") as f:
        lines = f.readlines()

    blocks = []
    current = []
    for line in lines:
        stripped = line.lstrip("\ufeff").strip()
        if stripped.startswith("#") or stripped.startswith(",#"):
            if current:
                blocks.append(current)
                current = []
            continue
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        # An annotated table header usually begins ,result,table,...
        if current and (stripped.startswith(",result,") or
                        stripped.startswith("result,table,")):
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)

    frames = []
    for block in blocks:
        try:
            item = pd.read_csv(StringIO("".join(block)))
            item.columns = item.columns.astype(str).str.strip()
            if "_time" in item.columns or "time" in item.columns:
                frames.append(item)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            pass
    if not frames:
        raise ValueError("Khong doc duoc bang du lieu trong Flux CSV")
    df = pd.concat(frames, ignore_index=True, sort=False)
else:
    df = pd.read_csv(str(INPUT_CSV), encoding="utf-8-sig")

df.columns = df.columns.astype(str).str.strip()
df = df.loc[:, ~df.columns.str.startswith("Unnamed:")]
df = df.rename(columns={"_time": "time"})

# Flux format: one sensor per row (_field, _value); pivot to one time row.
if "_field" in df.columns and "_value" in df.columns:
    if "device_id" not in df.columns:
        raise ValueError("Flux CSV thieu tag device_id. Hay export kem device_id")
    df = df[df["_field"].isin(SENSORS)].copy()
    df["_value"] = pd.to_numeric(df["_value"], errors="coerce")
    df = df.pivot_table(
        index=["time", "device_id"], columns="_field",
        values="_value", aggfunc="mean"
    ).reset_index()
    df.columns.name = None

required = ["time", "device_id"] + SENSORS
missing = [col for col in required if col not in df.columns]
if missing:
    raise ValueError("CSV thieu cot: {}. Cot dang co: {}".format(
        missing, list(df.columns)))

df = df.loc[df["device_id"].astype(str).str.strip() == DEVICE].copy()
if df.empty:
    raise ValueError("Khong co ban ghi trung TB_DEVICE_ID trong .env")
print("So ban ghi doc tu CSV:", len(df))
return df



def preprocess(df):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["time"]).set_index("time").sort_index()

    for sensor in SENSORS:
        df[sensor] = pd.to_numeric(df[sensor], errors="coerce")

    # Merge duplicate time rows, retaining mean for numeric sensor values.
    data = df[SENSORS].groupby(level=0).mean()
    if data.empty:
        raise ValueError("Khong co du lieu hop le de tien xu ly")

    print("\n--- DU LIEU BAN DAU ---")
    print(data.head())
    print("Gia tri thieu ban dau:\n", data.isna().sum().to_string())

    # Record outliers separately before marking them as missing.
    outlier_flags = pd.DataFrame(index=data.index)
    for sensor in SENSORS:
        s = data[sensor].dropna()
        if len(s) >= 4:
            q1, q3 = s.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                mask = (data[sensor] < low) | (data[sensor] > high)
            else:
                mask = pd.Series(False, index=data.index)
        else:
            mask = pd.Series(False, index=data.index)
        outlier_flags[sensor + "_outlier"] = mask.astype(int)
        print("{}: {} outlier".format(sensor, int(mask.sum())))
        data.loc[mask, sensor] = np.nan

    # Mean per minute. Empty minute windows become NaN.
    processed = data.resample("1min").mean()
    flags_per_min = outlier_flags.resample("1min").sum().astype(int)
    processed = processed.join(flags_per_min)

    print("\nGia tri thieu sau resampling:\n", processed[SENSORS].isna().sum().to_string())

    for sensor in SENSORS:
        # Fill only interior gaps, not the beginning or end of the series.
        processed[sensor] = processed[sensor].interpolate(
            method="time", limit_area="inside"
        )
        series = processed[sensor]
        processed[sensor + "_rolling"] = series.rolling(
            window=3, min_periods=1
        ).mean()
        processed[sensor + "_delta"] = series.diff()

        minimum, maximum = series.min(), series.max()
        if pd.notna(minimum) and pd.notna(maximum) and maximum > minimum:
            processed[sensor + "_norm"] = (series - minimum) / (maximum - minimum)
        elif pd.notna(minimum):
            # Constant valid signal: define normalized values as zero.
            processed[sensor + "_norm"] = 0.0
        else:
            processed[sensor + "_norm"] = np.nan

    print("\n--- DU LIEU SAU TIEN XU LY ---")
    print(processed.head(10).to_string())
    return processed


def save_data(df):
    points = []
    for timestamp, row in df.iterrows():
        point = (
            Point("sensor_processed")
            .tag("device_id", DEVICE)
            .time(timestamp.to_pydatetime(), WritePrecision.NS)
        )
        count = 0
        for field, value in row.items():
            if pd.notna(value) and np.isfinite(float(value)):
                point = point.field(field, float(value))
                count += 1
        if count:
            points.append(point)

    if not points:
        print("Khong co diem hop le de ghi")
        return

    with InfluxDBClient(url=URL, token=TOKEN, org=ORG) as client:
        writer = client.write_api(write_options=SYNCHRONOUS)
        writer.write(bucket=BUCKET, org=ORG, record=points)

    print("Da ghi {} diem vao sensor_processed".format(len(points)))


def main():
    print("BAT DAU TIEN XU LY IOT")
    raw = read_data()
    result = preprocess(raw)
    result.to_csv(str(OUTPUT_CSV), index_label="time", encoding="utf-8-sig")
    print("Da xuat:", OUTPUT_CSV.name)
    save_data(result)
    print("HOAN THANH TIEN XU LY!")


if __name__ == "__main__":
    main()