# IIoT 工业级物联网 AI 智能诊断与遥测中台
*(IIoT Industrial AI Diagnostic & Telemetry System)*

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-SocketIO-green.svg)](https://flask-socketio.readthedocs.io/)
[![MQTT](https://img.shields.io/badge/Protocol-MQTT-orange.svg)](https://mqtt.org/)
[![AI](https://img.shields.io/badge/AI_Agent-GLM--4-purple.svg)](https://open.bigmodel.cn/)

## 项目简介
本项目是一个端到端的工业物联网（IIoT）全栈解决方案。系统打通了从底层硬件感知（ESP32）、高频数据传输（MQTT）、后端并发处理（Flask + eventlet）到前端实时大屏（WebSocket）的全链路。

在基础遥测之上，系统创新性地引入了 **大语言模型（LLM）Agent**，实现了从传统的“固定阈值报警”向“动态智能诊断与维修建议”的工业 4.0 演进。

## 系统架构 (Architecture)

![System Architecture](3_Docs/architecture.svg)

**核心数据流闭环**：
ESP32 感知层 → MQTT Broker (10Hz+ 数据流) → Python 后端 (并发清洗与 AI 推理) → WebSocket (毫秒级推送) → Web 大屏渲染 & SQLite 持久化。

---

## 核心特性与工程亮点 (Core Highlights)

项目中不仅实现了基础的业务逻辑，更着重解决了**高并发并发、网络竞态、AI 调度控制**等硬核工程问题：

* **网络层深度调优 (Monkey Patch)**：深度定位并修复了 `eventlet` 协程环境下的 DNS 解析冲突 Bug，通过动态拦截清洗非法 Nameserver，保障了复杂网络下 MQTT 长连接的极高稳定性。
* **AI Agent 智能调度防抖**：针对高频工业数据流，独立设计了**“双重状态锁 (Double-Lock)”**与**冷却周期 (CD) 机制**。引入**Hysteresis（滞后区间算法）**过滤传感器数值抖动，将无效 AI Token 消耗降低 90% 以上。
* **生产数据崩溃恢复 (State Recovery)**：基于 SQLite 设计了高可靠的时序数据持久化方案。确保在硬件断线或后端服务异常重启后，产线累计产量（Count）能实现 100% 自动对齐与无损恢复。
* **毫秒级全双工流式推送**：利用多线程解耦 MQTT 阻塞消费与后端业务逻辑，通过 Flask-SocketIO 实现从物理异常触发到前端 DOM 渲染的 End-to-End 毫秒级低延迟响应。

---

## 硬件感知层与协议 (Hardware & Protocol)

### 接线规范 (ESP32)
| 模块 | ESP32 GPIO | 工业模拟作用 |
|---|---:|---|
| **按键 (Button)** | GPIO 14 | 短按：模拟计件产出 (+1)；长按：模拟设备故障中断 |
| **电位器 (Pot)** | GPIO 34 | ADC 采样，模拟设备核心温度波动 |
| **WS2812 灯环** | GPIO 27 | 边缘侧异常状态灯效警示 |
| **继电器 (Relay)** | GPIO 26 | 模拟执行器控制（风扇/急停） |
| **OLED 屏幕** | GPIO 21/22 | 边缘侧状态显示面板 |

*(底层中断与防抖逻辑详见 `1_Firmware/src/main.cpp`)*

### MQTT 通信规范
- **Broker**：`broker.emqx.io` (测试环境)
- **核心 Topic**：`factory/line1/data`
- **上报 Payload 示例**：
  ```json
  {
    "count": 1,
    "temp": 45.5,
    "status": "running"
  }
