"""IoT Lab 2 dashboard: visualize exported raw and processed CSV."""
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
RAW_CSV = BASE_DIR / "sensor_raw.csv"
PROCESSED_CSV = BASE_DIR / "processed_data.csv"

st.set_page_config(page_title="IoT Lab 2", layout="wide")
st.title("IoT Lab 2 - Sensor Monitoring")
st.caption("Wokwi -> ThingsBoard -> InfluxDB Cloud; local CSV dashboard")

@st.cache_data
def read_csv(path):
    df = pd.read_csv(str(path), encoding="utf-8-sig", comment="#")
    df.columns = df.columns.astype(str).str.strip()
    df = df.rename(columns={"_time": "time"})
    if "time" not in df.columns:
        raise ValueError("CSV requires a time column")
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    df = df.dropna(subset=["time"]).sort_values("time").set_index("time")
    return df

if not PROCESSED_CSV.exists():
    st.warning("Chua co processed_data.csv. Hay chay python preprocess.py truoc.")
    st.stop()

try:
    processed = read_csv(PROCESSED_CSV)
except Exception as exc:
    st.error("Khong doc duoc processed_data.csv: {}".format(exc))
    st.stop()

sensors = [key for key in ("temperature", "humidity", "distance_cm") if key in processed.columns]
if not sensors:
    st.error("CSV thieu cac cot cam bien temperature, humidity, distance_cm")
    st.stop()

st.sidebar.header("Tuy chon")
sensor = st.sidebar.selectbox("Cam bien", sensors)
st.sidebar.caption("Nhan R hoac Reload page de nap lai file CSV.")

c1, c2, c3 = st.columns(3)
series = pd.to_numeric(processed[sensor], errors="coerce")
c1.metric("So moc thoi gian", len(processed))
c2.metric("Gia tri moi nhat", "{:.2f}".format(series.dropna().iloc[-1]) if series.notna().any() else "N/A")
outlier_key = sensor + "_outlier"
c3.metric("Outliers", int(processed[outlier_key].fillna(0).sum()) if outlier_key in processed else 0)

columns = [name for name in (sensor, sensor+"_rolling") if name in processed.columns]
st.subheader("Du lieu sau xu ly va trung binh truot")
st.line_chart(processed[columns])

norm_key = sensor+"_norm"
if norm_key in processed.columns:
    st.subheader("Chuan hoa Min-Max")
    st.line_chart(processed[[norm_key]])

st.subheader("Bang du lieu")
st.dataframe(processed.tail(100), use_container_width=True)
st.download_button("Tai CSV da xu ly", data=PROCESSED_CSV.read_bytes(),
                   file_name="processed_data.csv", mime="text/csv")
st.info("Dashboard hien thi CSV da xuat; chua tu dong truy van real-time tu InfluxDB.")
