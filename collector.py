
import os
import time
import math
import requests

from dotenv import load_dotenv
from influxdb_client import (
    InfluxDBClient,
    Point,
    WritePrecision
)
from influxdb_client.client.write_api import SYNCHRONOUS

# ==========================================
# 1. ĐỌC CẤU HÌNH TỪ FILE .env
# ==========================================

load_dotenv()

TB_URL = os.environ["TB_URL"].rstrip("/")
TB_API_KEY = os.environ["TB_API_KEY"].strip()
DEVICE_ID = os.environ["TB_DEVICE_ID"]

KEYS = [
    key.strip()
    for key in os.environ["TB_KEYS"].split(",")
    if key.strip()
]

INFLUX_URL = os.environ["INFLUX_URL"]
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = os.environ["INFLUX_ORG"]
INFLUX_BUCKET = os.environ["INFLUX_BUCKET"]

POLL_SECONDS = 5
LOOKBACK_MS = 3600000  # Lấy lại 2 phút gần nhất

# ==========================================
# 2. KẾT NỐI THINGSBOARD
# ==========================================

session = requests.Session()

session.headers.update({
    "X-Authorization": f"ApiKey {TB_API_KEY}"
})

TB_API_URL = (
    f"{TB_URL}/api/plugins/telemetry/"
    f"DEVICE/{DEVICE_ID}/values/timeseries"
)


def get_telemetry():
    """Lấy dữ liệu lịch sử từ ThingsBoard."""

    end_ts = int(time.time() * 1000)
    start_ts = end_ts - LOOKBACK_MS

    response = session.get(
        TB_API_URL,
        params={
            "keys": ",".join(KEYS),
            "startTs": start_ts,
            "endTs": end_ts,
            "agg": "NONE",
            "limit": 1000,
            "orderBy": "ASC"
        },
        timeout=15
    )

    response.raise_for_status()
    return response.json()


# ==========================================
# 3. KIỂM TRA DỮ LIỆU
# ==========================================

def validate(key, value):
    """Kiểm tra và chuyển dữ liệu sang số."""

    try:
        value = float(value)
    except (ValueError, TypeError):
        return None

    if not math.isfinite(value):
        return None

    # Kiểm tra độ ẩm
    if key == "humidity":
        if not 0 <= value <= 100:
            return None

    # Kiểm tra nhiệt độ
    if key == "temperature":
        if not -40 <= value <= 80:
            return None

    # Khoảng cách không âm
    if key == "distance_cm":
        if value < 0:
            return None

    # Uptime và sequence không âm
    if key in ("uptime_s", "sequence"):
        if value < 0:
            return None

    return value


# ==========================================
# 4. KẾT NỐI INFLUXDB CLOUD
# ==========================================

influx_client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

writer = influx_client.write_api(
    write_options=SYNCHRONOUS
)

# Chống ghi lại dữ liệu trong cùng lần chạy.
# Sau khi restart, InfluxDB vẫn hợp nhất các
# điểm có cùng measurement, tag và timestamp.
saved = set()


# ==========================================
# 5. CHƯƠNG TRÌNH CHÍNH
# ==========================================

def main():
    print("================================")
    print("IOT LAB 2 - MQTT DATA PIPELINE")
    print("ThingsBoard REST -> InfluxDB")
    print("================================")
    print("Dang thu thap du lieu...")

    while True:
        try:
            data = get_telemetry()

            points = []
            pending_keys = set()

            for key, values in data.items():

                if key not in KEYS:
                    continue

                for item in values:
                    timestamp = int(item["ts"])
                    unique_key = (key, timestamp)

                    # Bỏ qua dữ liệu đã lưu
                    if unique_key in saved:
                        continue

                    value = validate(
                        key, item["value"]
                    )

                    if value is None:
                        print(
                            f"Du lieu khong hop le: {key}"
                        )
                        continue

                    point = (
                        Point("sensor_raw")
                        .tag("device_id", DEVICE_ID)
                        .field(key, value)
                        .time(
                            timestamp,
                            WritePrecision.MS
                        )
                    )

                    points.append(point)
                    pending_keys.add(unique_key)

            # Ghi InfluxDB
            if points:
                writer.write(
                    bucket=INFLUX_BUCKET,
                    org=INFLUX_ORG,
                    record=points
                )

                # Chỉ xác nhận sau khi ghi thành công
                saved.update(pending_keys)

                print(
                    f"Da luu {len(points)} gia tri"
                    " vao InfluxDB!"
                )

            else:
                print("Chua co du lieu moi.")

            # Xóa dấu vết các điểm quá cũ
            cutoff = (
                int(time.time() * 1000)
                - LOOKBACK_MS
            )

            saved.intersection_update({
                k for k in saved if k[1] >= cutoff
            })

        except requests.RequestException as e:
            print("Loi ThingsBoard:", e)

        except Exception as e:
            print("Loi xu ly/InfluxDB:", e)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDa dung chuong trinh.")
    finally:
        session.close()
        influx_client.close()
