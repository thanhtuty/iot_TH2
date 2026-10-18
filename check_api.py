
import os
import requests
from dotenv import load_dotenv

# Đọc lại nội dung file .env
load_dotenv(override=True)

TB_URL = os.getenv("TB_URL", "").strip().rstrip("/")
API_KEY = os.getenv("TB_API_KEY", "").strip()

print("ThingsBoard URL:", TB_URL)
print("Co API Key:", bool(API_KEY))
print("API Key bat dau bang tb_:", API_KEY.startswith("tb_"))
print("Do dai API Key:", len(API_KEY))

# Không in toàn bộ API Key ra Terminal
headers = {
    "X-Authorization": f"ApiKey {API_KEY}"
}

url = f"{TB_URL}/api/auth/user"

try:
    response = requests.get(
        url,
        headers=headers,
        timeout=15
    )

    print("HTTP Status:", response.status_code)

    if response.status_code == 200:
        print("XAC THUC THANH CONG!")
        print("Python da ket noi ThingsBoard.")

    elif response.status_code == 401:
        print("API Key khong duoc chap nhan.")
        print("Kiem tra lai API Key trong .env.")

    elif response.status_code == 403:
        print("API Key khong co quyen truy cap.")

    else:
        print("Loi:", response.status_code)
        print(response.text[:300])

except requests.RequestException as e:
    print("Loi ket noi:", e)
