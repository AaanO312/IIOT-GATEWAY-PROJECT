# 🏭 工业物联网 (IIoT) 产线监控网关

![PlatformIO](https://img.shields.io/badge/Platform-PlatformIO-orange)
![Backend](https://img.shields.io/badge/Backend-Python%20Flask-blue)
![Frontend](https://img.shields.io/badge/Frontend-Socket.IO-yellow)
![Hardware](https://img.shields.io/badge/Hardware-ESP32-green)

这是一个基于 **ESP32** 和 **Web 技术** 的全栈物联网项目。它模拟了一个真实的工厂生产场景，实现了从**传感器数据采集**、**边缘端控制**、**MQTT 数据传输**到**Web 端实时可视化**的完整流程。

---

## 📖 项目背景与目标

在传统的工厂产线中，数据往往滞后，且设备故障难以实时发现。本项目旨在开发一个**低成本、低延迟**的物联网网关原型，主要解决以下问题：
1.  **数据可视化**：将产线的产量、温度等数据实时投屏到浏览器，无需人工抄录。
2.  **边缘控制**：当设备过热时，无需等待云端指令，网关在本地自动启动风扇降温（安全机制）。
3.  **远程报警**：设备故障时，第一时间通知后台，并在大屏上显示报警信息。

---

## 📐 系统架构图

数据流向：`传感器` -> `ESP32 (边缘层)` -> `MQTT Broker (传输层)` -> `Python Flask (应用层)` -> `浏览器 (展示层)`

![System Architecture](3_Docs/architecture.svg)

---

## ✨ 核心功能详解

### 1. 边缘计算 (Edge Computing)
ESP32 不仅仅是传声筒，它在本地处理了核心逻辑：
*   **按键消抖**: 编写了软件算法，防止机械按键抖动导致产量误计。
*   **本地闭环**: 实时监测温度，一旦超过 **80°C**，直接吸合继电器（启动风扇），**断网状态下依然有效**，保证设备安全。
*   **状态指示**: 通过 WS2812 灯环的不同颜色（绿呼吸/红旋转）直观反馈设备运行状态。

### 2. 实时通信 (Real-time Communication)
*   **MQTT 协议**: 摒弃了传统的 HTTP 轮询，采用轻量级的 MQTT 协议，带宽占用极低，适合工业环境。
*   **WebSocket**: 后端与前端网页之间使用 Socket.IO 连接，数据变化毫秒级同步，网页**无需刷新**即可看到数字跳动。

### 3. 全栈监控 (Full-stack Monitoring)
*   **OLED 屏幕**: 现场工人可以看到当前的 IP 地址、MQTT 连接状态和实时温度。
*   **Web 看板**: 远程管理人员可以通过电脑/手机浏览器查看产量曲线和报警信息。

---

## 🛠️ 硬件清单与接线

| 硬件模块 | ESP32 引脚 | 功能说明 |
| :--- | :--- | :--- |
| **主控板** | ESP32 DevKit V1 | 双核处理器，集成 WiFi/蓝牙 |
| **0.96" OLED** | SDA:21 / SCL:22 | 显示本地调试信息 |
| **WS2812 灯环** | GPIO 27 | RGB 全彩状态指示 |
| **按键 (Button)** | GPIO 14 | 短按：增加产量 / 长按：模拟故障 |
| **电位器 (Pot)** | GPIO 34 | 模拟温度传感器的电压变化 |
| **继电器 (Relay)** | GPIO 26 | 控制 5V 散热风扇 |

---

## 🚀 部署与运行指南

### 第一步：固件烧录 (Firmware)
1.  使用 **VS Code** (需安装 PlatformIO 插件) 打开 `1_Firmware` 文件夹。
2.  打开 `src/main.cpp`，修改以下配置：
    ```cpp
    const char* ssid = "你的WiFi名称";
    const char* password = "你的WiFi密码";
    const char* mqtt_server = "broker.emqx.io"; // 默认使用公共服务器
    ```
3.  连接 ESP32 开发板，点击底部的 `➡️ Upload` 按钮。
4.  烧录成功后，OLED 屏幕将显示 "Connecting WiFi..."。

### 第二步：后端服务 (Backend)
1.  确保电脑已安装 **Python 3.8+**。
2.  进入后端目录并安装依赖：
    ```bash
    cd 2_Backend
    pip install -r requirements.txt
    ```
3.  启动服务器：
    ```bash
    python app.py
    ```
    *看到 "Backend Running..." 字样即表示启动成功。*

### 第三步：系统联调
1.  打开浏览器访问：`http://localhost:5000`。
2.  **测试产量**：按下 ESP32 上的按键，网页上的“当前产量”会立即 +1。
3.  **测试温控**：旋转电位器，当屏幕温度超过 80°C 时，继电器吸合（风扇转动），网页显示“高温报警”。

---

## 📡 数据协议文档

设备与服务器之间采用 **JSON** 格式交互，Topic 为 `factory/line1/data`。

**数据包示例：**
```json
{
  "count": 105,       // 当前累计产量 (int)
  "temp": 42.5,       // 当前设备温度 (float)
  "status": "running" // 运行状态: "running"(正常) | "fault"(故障)
}
