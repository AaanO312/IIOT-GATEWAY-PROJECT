import eventlet
eventlet.monkey_patch()


from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
import json
import threading
import sqlite3
import time
from datetime import datetime


# --- 配置 ---
#MQTT_BROKER = "127.0.0.1"
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC_DATA = "factory/line1/data"
DB_FILE = "factory.db"


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
last_trigger_time = 0 # [新增] 上次处理消息的时间

# 全局内存数据 (用于实时显示)
realtime_data = {
    "count": 0,
    "temperature": 25,
    "oee": 100.0,
    "status": "idle"
}


# --- 数据库初始化函数 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 创建表：如果不存在则创建
    c.execute('''CREATE TABLE IF NOT EXISTS production_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  count_inc INTEGER,
                  temperature REAL,
                  status TEXT)''')
    conn.commit()
    conn.close()
    print(">> 数据库已初始化")


# --- 数据库写入函数 ---
def save_to_db(count_inc, temp, status):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO production_log (count_inc, temperature, status) VALUES (?, ?, ?)",
                  (count_inc, temp, status))
        conn.commit()
        conn.close()
        print(f"✅ 数据已入库: +{count_inc}") # <--- 加这行
    except Exception as e:
        print(f"DB Error: {e}")

@socketio.on('connect')
def handle_connect():
    print('>> 前端页面已连接，正在同步当前状态...')
    # 关键：新用户连上来，立刻把当前的 realtime_data 发给它
    emit('update_data', realtime_data) 


# --- HTML 模板 (增加了历史查询 API 调用) ---
# --- 替换原来的 HTML_TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IIoT 数据中心</title>
    <meta charset="utf-8">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body { background-color: #0b1120; color: white; font-family: 'Segoe UI', sans-serif; text-align: center; }
        .dashboard { display: flex; justify-content: space-around; margin-top: 30px; }
        .card { background: #1f2937; padding: 20px; border-radius: 10px; width: 22%; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h1 { color: #60a5fa; margin-bottom: 10px; }
        .value { font-size: 42px; font-weight: bold; color: #34d399; transition: color 0.3s; }
        .label { color: #9ca3af; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
        .status-bar { background: #111827; padding: 10px; font-size: 12px; color: #6b7280; }
        #chart { width: 90%; height: 400px; margin: 30px auto; background: #1f2937; border-radius: 10px; padding: 10px; }
        
        /* 报警闪烁动画 */
        .alarm {
            color: #ef4444 !important; /* 强制变红 */
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <h1>🏭 工业物联网数据中心</h1>
    <div class="status-bar">架构: MQTT + Flask + SQLite | 状态: <span id="conn-status" style="color:green">在线</span></div>
    
    <div class="dashboard">
        <!-- 产量卡片 -->
        <div class="card">
            <div class="label">Total Production</div>
            <div id="count" class="value">0</div>
        </div>
        
        <!-- OEE卡片 -->
        <div class="card">
            <div class="label">Efficiency (OEE)</div>
            <div id="oee" class="value">100%</div>
        </div>
        
        <!-- [新增] 温度卡片 -->
        <div class="card">
            <div class="label">Temperature</div>
            <div id="temp" class="value">25.0°C</div>
        </div>


        <!-- 状态卡片 -->
        <div class="card">
            <div class="label">Machine Status</div>
            <div id="status" class="value" style="color:#60a5fa">IDLE</div>
        </div>
    </div>
    
    <div id="chart"></div>


    <script>
        var socket = io();
        var myChart = echarts.init(document.getElementById('chart'));
        
        // 记录上一次的状态
        var lastChartCount = -1; 
        var lastStatus = ""; // [新增] 记录上一次状态


        var option = {
            backgroundColor: '#1f2937',
            title: { text: '实时产能趋势', left: 'center', textStyle: { color: '#fff' } },
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'category', data: [], axisLabel: { color: '#9ca3af' } },
            yAxis: { type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151' } } },
            series: [{ name: '产量', data: [], type: 'line', smooth: true, areaStyle: { opacity: 0.2 }, color: '#34d399' }]
        };
        myChart.setOption(option);


        socket.on('connect', function() { console.log("Connected"); });


        socket.on('update_data', function(msg) {
            // 1. 更新文字 (保持不变)
            document.getElementById('count').innerText = msg.count;
            document.getElementById('oee').innerText = msg.oee.toFixed(1) + "%";
            document.getElementById('temp').innerText = msg.temperature + "°C";
            
            var tempDiv = document.getElementById('temp');
            var statusDiv = document.getElementById('status');
            
            // 状态样式逻辑
            tempDiv.classList.remove('alarm');
            statusDiv.classList.remove('alarm');
            statusDiv.style.color = '#34d399';


            if (msg.temperature > 80) {
                statusDiv.innerText = "OVERHEAT";
                statusDiv.classList.add('alarm');
                tempDiv.classList.add('alarm');
            } else if (msg.status === 'fault') {
                statusDiv.innerText = "FAULT";
                statusDiv.classList.add('alarm');
                statusDiv.style.color = '#ef4444';
            } else {
                statusDiv.innerText = "RUNNING";
            }


            // 2. [核心修改] 图表更新条件：产量变了 OR 状态变了
            // 这样长按报错时，图表也会平移记录
            if (msg.count != lastChartCount || msg.status != lastStatus) {
                
                // 如果是第一次加载，或者真的有变化
                if (lastChartCount != -1) { 
                    var now = new Date().toLocaleTimeString();
                    option.xAxis.data.push(now);
                    option.series[0].data.push(msg.count);
                    
                    if(option.xAxis.data.length > 20) {
                        option.xAxis.data.shift();
                        option.series[0].data.shift();
                    }
                    myChart.setOption(option);
                }
                
                // 更新记录
                lastChartCount = msg.count;
                lastStatus = msg.status;
            }
        });
        
        // 初始化
        fetch('/api/history').then(r=>r.json()).then(d=>{
            if(d.total_count) lastChartCount = d.total_count;
        });
    </script>


</body>
</html>
"""



@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


# --- 新增：历史数据接口 ---
@app.route('/api/history')
def get_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 查询总产量 (把所有 count_inc 加起来)
    c.execute("SELECT SUM(count_inc) FROM production_log")
    total = c.fetchone()[0]
    conn.close()
    
    # 如果数据库是空的，total可能是None
    if total is None: total = 0
    
    # 同步到内存变量，防止页面刷新后归零
    realtime_data['count'] = total
    
    return jsonify({"total_count": total})




# --- MQTT 回调 ---
def on_connect(client, userdata, flags, rc):
    print(f">> MQTT 连接成功")
    client.subscribe(MQTT_TOPIC_DATA)


def on_message(client, userdata, msg):
    global realtime_data, last_trigger_time
    
    try:
        if msg.retain: return
        
        # 1. 先解析数据，看看是什么类型的消息
        payload = json.loads(msg.payload.decode())
        print(f">> 收到: {payload}")
        
        count_inc = 0
        if 'count' in payload:
            count_inc = int(payload['count'])


        # 2. 【智能防抖逻辑】 (核心修改)
        # 只有当这是一个“产量增加”的消息时，才检查防抖
        if count_inc > 0:
            current_time = time.time()
            # 如果距离上次“有效产量”不到 0.2 秒，认为是抖动
            if current_time - last_trigger_time < 0.2:
                print(f">> 拦截重复计数 (抖动)")
                return
            # 更新上次有效计数的时间
            last_trigger_time = current_time


        # 3. 处理数据
        status = payload.get('status', realtime_data['status'])
        temp = payload.get('temp', realtime_data['temperature'])
        
        realtime_data['status'] = status
        realtime_data['temperature'] = temp


        # 4. 存库逻辑
        if count_inc > 0:
            save_to_db(count_inc, temp, status)
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT SUM(count_inc) FROM production_log")
                total = c.fetchone()[0]
                if total: realtime_data['count'] = total
                print(f">> 数据库最新总数: {total}")
                
        elif 'status' in payload:
             save_to_db(0, temp, status)


        # 5. 推送
        socketio.emit('update_data', realtime_data)
        
    except Exception as e:
        print(f"错误: {e}")



# --- 主程序 ---
def run_mqtt():
    client = mqtt.Client(clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()



if __name__ == '__main__':
    init_db() # 启动时先建表
    
    # 读取一下历史总数，恢复现场
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(count_inc) FROM production_log")
        res = cursor.fetchone()[0]
        if res: realtime_data['count'] = res


    mqtt_thread = threading.Thread(target=run_mqtt)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    print(">> 系统启动完成。访问 http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
