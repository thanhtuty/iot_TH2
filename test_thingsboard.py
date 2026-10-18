
import os
import requests
from dotenv import load_dotenv

# 1. Đọc cấu hình
load_dotenv()

TB_URL = os.environ["TB_URL"].rstrip("/")
API_KEY = os.environ["TB_API_KEY"]
DEVICE_ID = os.environ["TB_DEVICE_ID"]
KEYS = os.environ["TB_KEYS"]

# 2. Xác thực qua API Key
headers = {
    "X-Authorization": f"ApiKey {API_KEY}"
}

# 3. Tạo URL lấy dữ liệu telemetry
url = (
    f"{TB_URL}/api/plugins/telemetry/"
    f"DEVICE/{DEVICE_ID}/values/timeseries"
)

try:
    print("Đang kết nối ThingsBoard...")

    response = requests.get(
        url,
        headers=headers,
        params={"keys": KEYS},
        timeout=15
    )

    print("HTTP Status:", response.status_code)

    response.raise_for_status()

    data = response.json()

    print("\nDỮ LIỆU CẢM BIẾN:")

    if not data:
        print("Không có dữ liệu telemetry.")
    else:
        for key, values in data.items():
            for item in values:
                print(
                    f"{key}: {item['value']} "
                    f"| timestamp: {item['ts']}"
                )

except requests.exceptions.HTTPError as e:
    print("Lỗi HTTP:", e)
    print("Phản hồi:", response.text[:500])

except requests.exceptions.RequestException as e:
    print("Lỗi kết nối:", e)
