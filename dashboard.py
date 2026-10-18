"""Lightweight IoT dashboard for Python 3.8 (32-bit): Flask + Chart.js."""
from pathlib import Path

import pandas as pd
from flask import Flask, Response, jsonify, render_template_string, request

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "processed_data.csv"
SENSORS = ("temperature", "humidity", "distance_cm")
app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IoT Lab 2 Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
body{font-family:Arial,sans-serif;background:#f5f7fb;color:#17253b;margin:0}
main{max-width:1050px;margin:auto;padding:26px 18px}
h1{margin:0 0 8px}p{color:#52627a}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}
select,button,a.btn{padding:10px 14px;border:1px solid #d1d9e5;border-radius:9px;background:white;font:inherit}
button{cursor:pointer}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.card,.panel{background:white;padding:17px;border-radius:13px;box-shadow:0 2px 8px #0d244414}
.card strong{display:block;font-size:25px;margin-top:8px}.panel{margin-top:16px}
.chart-wrap{height:310px}.note{font-size:13px}.error{color:#a40020}
@media(max-width:650px){.grid{grid-template-columns:1fr}.chart-wrap{height:240px}}
</style></head>
<body><main>
<h1>IoT Lab 2 - Dashboard</h1>
<p>Wokwi ESP32 → ThingsBoard → InfluxDB → dữ liệu tiền xử lý (CSV)</p>
<div class="toolbar"><label>Cảm biến: <select id="sensor">
<option value="temperature">Nhiệt độ (°C)</option>
<option value="humidity">Độ ẩm (%)</option>
<option value="distance_cm">Khoảng cách (cm)</option>
</select></label><button onclick="reload()">Làm mới dữ liệu</button>
<a class="btn" href="/download">Tải processed_data.csv</a></div>
<div id="error" class="error"></div>
<section class="grid">
<div class="card">Số mốc thời gian<strong id="count">—</strong></div>
<div class="card">Giá trị mới nhất<strong id="latest">—</strong></div>
<div class="card">Số outlier<strong id="outliers">—</strong></div>
</section>
<div class="panel"><h3>Dữ liệu cảm biến và trung bình trượt</h3>
<div class="chart-wrap"><canvas id="mainChart"></canvas></div></div>
<div class="panel"><h3>Chuẩn hóa Min-Max</h3>
<div class="chart-wrap"><canvas id="normChart"></canvas></div></div>
<p class="note">Dữ liệu đọc từ processed_data.csv, không phải telemetry trực tiếp. Cần chạy lại preprocess.py để cập nhật CSV. Biểu đồ sử dụng Chart.js qua CDN (cần Internet).</p>
</main><script>
let mainChart=null,normChart=null;
function draw(old,canvas,datasets,labels){
  if(old)old.destroy();
  if(typeof Chart==='undefined'){document.getElementById('error').textContent='Không tải được Chart.js. Hãy kiểm tra Internet.';return null;}
  return new Chart(document.getElementById(canvas),{type:'line',
    data:{labels:labels,datasets:datasets},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    scales:{x:{ticks:{maxTicksLimit:8}},y:{beginAtZero:false}}}});
}
async function reload(){
 const sensor=document.getElementById('sensor').value;
 const el=document.getElementById('error');el.textContent='';
 try{
 const res=await fetch('/api/data?sensor='+encodeURIComponent(sensor));
 const data=await res.json();if(!res.ok)throw new Error(data.error||'Không đọc được CSV');
 document.getElementById('count').textContent=data.count;
 document.getElementById('latest').textContent=data.latest===null?'N/A':data.latest.toFixed(2);
 document.getElementById('outliers').textContent=data.outliers;
 mainChart=draw(mainChart,'mainChart',[
 {label:sensor,data:data.values,borderColor:'#2563eb',spanGaps:false,tension:.18},
 {label:'Trung bình trượt',data:data.rolling,borderColor:'#f97316',spanGaps:false,tension:.18}
 ],data.labels);
 normChart=draw(normChart,'normChart',[
 {label:'Min-Max [0,1]',data:data.normalized,borderColor:'#16a34a',spanGaps:false,tension:.18}
 ],data.labels);
 }catch(err){el.textContent=err.message;}
}
document.getElementById('sensor').addEventListener('change',reload);reload();
</script></body></html>
"""


def load_processed():
    if not CSV_PATH.is_file():
        raise FileNotFoundError(
            "Chua co processed_data.csv. Hay chay preprocess.py truoc."
        )
    df = pd.read_csv(str(CSV_PATH), encoding="utf-8-sig")
    df.columns = df.columns.astype(str).str.strip()
    df = df.rename(columns={"_time": "time"})
    if "time" not in df.columns:
        raise ValueError("CSV thieu cot time")
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")
    return df


def to_values(df, column):
    if column not in df.columns:
        return [None] * len(df)
    values = pd.to_numeric(df[column], errors="coerce")
    return [None if pd.isna(v) else float(v) for v in values]


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/data")
def data():
    sensor = request.args.get("sensor", "temperature")
    if sensor not in SENSORS:
        return jsonify(error="Cam bien khong hop le"), 400
    try:
        df = load_processed()
        if sensor not in df.columns:
            raise ValueError("CSV thieu cot {}".format(sensor))
        values = to_values(df, sensor)
        valid = [v for v in values if v is not None]
        outliers = to_values(df, sensor + "_outlier")
        return jsonify(
            count=len(df),
            labels=df["time"].dt.strftime("%d/%m %H:%M").tolist(),
            values=values,
            rolling=to_values(df, sensor + "_rolling"),
            normalized=to_values(df, sensor + "_norm"),
            latest=valid[-1] if valid else None,
            outliers=int(sum(v for v in outliers if v is not None)),
        )
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
        return jsonify(error=str(exc)), 400


@app.route("/download")
def download():
    if not CSV_PATH.is_file():
        return Response("Chua co processed_data.csv", status=404)
    return Response(
        CSV_PATH.read_bytes(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="processed_data.csv"'},
    )


if __name__ == "__main__":
    print("Mo dashboard: http://127.0.0.1:8501")
    app.run(host="127.0.0.1", port=8501, debug=False)
