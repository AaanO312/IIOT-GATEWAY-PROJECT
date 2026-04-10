import os
# 核心指令：强制禁用 eventlet 那个带 Bug 的自定义 DNS 解析器
os.environ['EVENTLET_NO_GREENDNS'] = 'yes'

import eventlet
eventlet.monkey_patch()

from paho.mqtt.enums import CallbackAPIVersion
from agent import ask_agent
from flask import Flask,request, render_template_string, jsonify
from flask_socketio import SocketIO, emit

import dns.resolver
# 记录原始的解析方法
original_enrich = dns.resolver.Resolver._enrich_nameservers
def patched_enrich(self, nameservers, ports, port):
    # 过滤掉任何带有分号或非法格式的 DNS 地址
    clean_ns = []
    for ns in nameservers:
        if isinstance(ns, str) and ';' not in ns and ns.strip():
            clean_ns.append(ns)
    return original_enrich(self, clean_ns, ports, port)
import paho.mqtt.client as mqtt
import json
import threading
import sqlite3
import time
from datetime import datetime


# --- 配置 ---
MQTT_BROKER = "broker.emqx.io"
#MQTT_BROKER = "54.153.51.199"
MQTT_PORT = 1883
MQTT_TOPIC_DATA = "factory/line1/data"
DB_FILE = "factory.db"


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
last_trigger_time = 0 #上次处理消息的时间
last_ai_time = 0
is_ai_running = False
is_alerting = False

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
        print(f"数据已入库: +{count_inc}") # <--- 加这行
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
    <h1>工业物联网数据中心</h1>
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
        
        <!-- 温度卡片 -->
        <div class="card">
            <div class="label">Temperature</div>
            <div id="temp" class="value">25.0°C</div>
        </div>


        <!-- 状态卡片 -->
        <div class="card">
            <div class="label">Machine Status</div>
            <div id="status" class="value" style="color:#60a5fa">IDLE</div>
        </div>

        <div id="ai-report-box" style="width: 90%; margin: 20px auto; padding: 15px; background: #1e293b; border-left: 5px solid #3b82f6; text-align: left; display: none;">
            <h3 style="color: #60a5fa; margin-top: 0;">AI 智能诊断建议</h3>
            <div id="ai-content" style="line-height: 1.6; color: #e2e8f0;">正在生成分析报告...</div>
        </div>
    </div>
    
    <div id="chart"></div>


    <script>
        var socket = io();
        var myChart = echarts.init(document.getElementById('chart'));
        
        // 记录上一次的状态
        var lastChartCount = -1; 
        var lastStatus = ""; // 记录上一次状态


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
            // 1. 更新文字 
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


            // 2. 图表更新条件：产量变了 OR 状态变了
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

        // 监听 AI 传来的诊断信息
        socket.on('ai_analysis', function(msg) {
            var box = document.getElementById('ai-report-box');
            var content = document.getElementById('ai-content');
    
            if (msg.action === 'clear' || msg.content.includes("恢复正常")) {
                // 【绿灯】恢复正常
                content.innerText = msg.content;
                box.style.borderLeftColor = "#3b82f6"; // 边框变回蓝色
                box.style.animation = "none";
                setTimeout(function() { box.style.display = 'none'; }, 3000);
                
            } else if (msg.action === 'loading') {
                // 【红灯持续闪烁】温度刚上去，AI 正在想
                box.style.display = 'block'; 
                content.innerText = msg.content;
                box.style.borderLeftColor = "#ef4444"; // 边框变血红
                box.style.animation = "blink 1s infinite"; // 持续闪烁，直到报告出来
                
            } else {
                // 【红灯常亮】报告出来了，供人阅读
                box.style.display = 'block'; 
                content.innerText = msg.content;
                box.style.borderLeftColor = "#ef4444"; 
                box.style.animation = "none"; // 停止闪烁，以免晃眼影响阅读
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


# --- 历史数据接口 ---
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

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    # 从你现有的全局变量 realtime_data 获取数据
    temp = realtime_data['temperature']
    status = realtime_data['status']
    
    # 得到 AI 的回复
    answer = ask_agent(user_msg, temp, status)
    return jsonify({"reply": answer})


# --- MQTT 回调 ---
def on_connect(client, userdata, flags, rc):
    print(f">> MQTT 连接成功")
    client.subscribe(MQTT_TOPIC_DATA)


def on_message(client, userdata, msg):
    global realtime_data, last_trigger_time, last_ai_time, is_alerting
    
    try:
        if msg.retain: return
        payload = json.loads(msg.payload.decode())
        
        # 1. 立即更新最新的实时数据（统一数据源）
        if 'temp' in payload:
            realtime_data['temperature'] = payload['temp']
        if 'status' in payload:
            realtime_data['status'] = payload['status']
        
        # 获取最新快照
        temp = realtime_data['temperature']
        status = realtime_data['status']
        count_inc = payload.get('count', 0)

        # 2. 产量计数逻辑（保持原有的防抖）
        if count_inc > 0:
            current_time = time.time()
            if current_time - last_trigger_time < 0.2:
                return
            last_trigger_time = current_time
            save_to_db(count_inc, temp, status)
            # 更新总数
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT SUM(count_inc) FROM production_log")
                total = c.fetchone()[0]
                if total: realtime_data['count'] = total

        # 3. AI 诊断触发逻辑（增加状态屏障）
        # 只有在 高温 或 故障 且 AI 没有正在运行时才触发
        if (temp > 80 or status == 'fault'):
            if not is_alerting and not is_ai_running:
                # 传入最新的 temp 和 status
                is_alerting = True
                threading.Thread(target=ai_task, args=(temp, status)).start()
        
        # 只有在 彻底安全 且 之前处于报警 CD 状态时才重置
        elif temp < 60 and status != 'fault':
            # 只有当 last_ai_time 不为 0 时才发清除指令，避免每秒重复发送 clear
            if is_alerting:
                is_alerting = False
                last_ai_time = 0
                socketio.emit('ai_analysis', {
                    'content': "系统状态恢复正常。",
                    'action': 'clear'
                })
                print(">>状态恢复，警报已清除")

        # 4. 同步更新前端仪表盘
        socketio.emit('update_data', realtime_data)
        
    except Exception as e:
        print(f"处理消息错误: {e}")

def ai_task(temp, status):
    global last_ai_time, is_ai_running , is_alerting
    
    # 1. 【核心防御】如果 AI 正在思考，直接拦截，一分钱都不多花！
    if is_ai_running:
        return
        
    current_time = time.time()
    if current_time - last_ai_time < 300:
        return

    # 2. 上锁，并立刻更新时间戳 (非常关键！)
    is_ai_running = True
    last_ai_time = time.time() 
    
    # 3. 通知前端：AI 正在写报告，赶紧闪烁红灯！
    if temp > 80:
        # 高温报警逻辑
        loading_msg = f"温度警报：检测到异常高温 ({temp}℃)！正在分析降温方案..."
        prompt = "警告：检测到工业生产线设备温度异常超标（过热），请提供专业的故障原因分析及降温操作建议。"
    elif status == 'fault':
        # 故障报警逻辑 (即使温度正常也会触发)
        loading_msg = f"硬件故障警报：底层系统触发 FAULT 宕机状态！正在排查主板与传感器..."
        prompt = "警告：工业设备报告了底层逻辑故障（状态为 FAULT），虽然温度未超标，但系统已停止运行。请分析导致底层系统报错、传感器失灵或电路异常的可能原因，并给出维修步骤。"

    socketio.emit('ai_analysis', {
        'content': loading_msg, 
        'action': 'loading'
    })

    try:
        advice = ask_agent(prompt, temp, status)
        # 4. 报告生成完毕，发送给前端
        socketio.emit('ai_analysis', {'content': advice, 'action': 'done'})
    except Exception as e:
        print(f"调用失败: {e}")
    finally:
        # 5. 无论成功失败，最后都要解锁，保证下次还能调用
        is_ai_running = False

# --- 主程序 ---
def run_mqtt():
    client = mqtt.Client(CallbackAPIVersion.VERSION1, clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message
    print(f">> 正在连接 MQTT 服务器: {MQTT_BROKER} ...")
    client.connect(MQTT_BROKER, MQTT_PORT, 120)
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
