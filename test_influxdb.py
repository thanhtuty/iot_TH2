
import os
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()

url = os.environ["INFLUX_URL"]
token = os.environ["INFLUX_TOKEN"]
org = os.environ["INFLUX_ORG"]
bucket = os.environ["INFLUX_BUCKET"]

with InfluxDBClient(
    url=url,
    token=token,
    org=org
) as client:

    print("Kiem tra ket noi InfluxDB...")

    # Kiểm tra server
    print("Server ready:", client.ping())

    # Ghi một bản ghi thử nghiệm
    point = (
        Point("sensor_test")
        .tag("device_id", "esp32_test")
        .field("temperature", 25.0)
    )

    writer = client.write_api(
        write_options=SYNCHRONOUS
    )

    writer.write(
        bucket=bucket,
        org=org,
        record=point
    )

    print("GHI DU LIEU THANH CONG!")
