# IoT Lab 2 - Thu thap, luu tru va tien xu ly du lieu IoT

## Kien truc
Wokwi ESP32 -> MQTT -> ThingsBoard Cloud -> Python (REST polling) -> InfluxDB Cloud (`sensor_raw`).

Tien xu ly: xuat `sensor_raw.csv` tu InfluxDB, chay Pandas (IQR, resampling 1 phut, noi suy, rolling mean, delta, Min-Max) va ghi `sensor_processed`. Dashboard Streamlit hien thi file CSV da xu ly.

**Gioi han:** Python dung REST API ThingsBoard, chua dap ung yeu cau Python MQTT subscribe truc tiep. Dashboard hien CSV, khong phai real-time. Buoc xuat CSV can lam lai khi co du lieu moi.

## Chay tren Windows (Python 3.8)
```bat
cd /d C:\Users\Admin\Desktop\IoT_Lab2
python -m pip install -r requirements.txt
copy .env.example .env
```
Mo `.env` va dien token/API key moi (khong chia se cho nguoi khac).

1. Chay Wokwi va kiem tra Latest telemetry tren ThingsBoard.
2. `python test_thingsboard.py` - kiem tra REST.
3. `python test_influxdb.py` - kiem tra ghi InfluxDB.
4. `python collector.py` - dong bo telemetry sang InfluxDB.
5. Vao InfluxDB Cloud Data Explorer, truy van:
```sql
SELECT time, device_id, temperature, humidity, distance_cm
FROM "sensor_raw"
ORDER BY time ASC
```
Tai ket qua CSV va luu tai thu muc du an voi ten `sensor_raw.csv`. Can co cac cot `time, device_id, temperature, humidity, distance_cm` (hoac annotated Flux CSV co `_time, _field, _value, device_id`).
6. `python preprocess.py` - tao `processed_data.csv` va ghi `sensor_processed`.
7. `python -m streamlit run dashboard.py` - xem dashboard.

## Cau truc
- `collector.py`: ThingsBoard REST -> InfluxDB
- `preprocess.py`: CSV -> IQR -> resampling -> interpolation -> features -> InfluxDB
- `dashboard.py`: Dashboard tu processed_data.csv
- `.env.example`: Mau bien moi truong, khong chua secret
- `.gitignore`: Loai tru .env va CSV sinh ra

## Bao mat
Khong commit `.env`, access token, mat khau hoac credentials. Thu hoi moi token da tung bi chia se. Repository public thi can kiem tra lich su Git neu secret tung duoc commit.
