# IIoT Gateway Demo（工业物联网产线监控小项目）

这是我的第一个物联网/软件结合项目：用 **ESP32** 模拟产线数据采集，通过 **MQTT** 上报到电脑端 **Python Flask 后端**，并在网页上实时展示（Socket.IO + ECharts），同时把数据存入 **SQLite** 数据库。

## 系统架构

![System Architecture](3_Docs/architecture.svg)

数据流大致如下：

设备侧（ESP32） → MQTT Broker → 后端（Flask + MQTT Client）→ WebSocket 推送 → 浏览器看板  
并且后端会将产量、温度、状态写入 SQLite。

---

## 项目功能

- **按键计数**：按一下按钮模拟生产一次，产量 +1，并上报 MQTT
- **温度模拟**：电位器模拟温度，ESP32 定时上报温度
- **故障模拟**：长按按钮触发故障状态（fault），网页端报警闪烁
- **过热保护**：温度超过阈值时进入过热状态（OVERHEAT），网页端显示报警（并可在设备端控制继电器风扇）
- **网页实时看板**：
  - 显示产量、温度、OEE（演示用）、设备状态
  - ECharts 折线图实时显示产量趋势（最近 20 个点）
- **数据持久化**：后端用 SQLite 保存日志；页面刷新后通过 `/api/history` 恢复累计产量
- **防抖逻辑**：后端对短时间内重复的 `count` 增量消息进行过滤，避免误计数

---

## 硬件与接线（ESP32）

| 模块 | ESP32 GPIO | 作用 |
|---|---:|---|
| 按键 Button | GPIO 14 | 短按：产量+1；长按：故障 |
| OLED | GPIO 21 (SDA) / 22 (SCL) | 显示状态 |
| WS2812 灯环 | GPIO 27 | 状态灯效 |
| 电位器 Pot | GPIO 34 | 模拟温度（ADC） |
| 继电器 Relay | GPIO 26 | 风扇/执行器控制 |

> 具体逻辑以 `1_Firmware/src/main.cpp` 为准。

---

## MQTT 通信

- Broker：`broker.emqx.io`
- Topic：`factory/line1/data`

设备侧发送 JSON 示例：

```json
{
  "count": 1,
  "temp": 45.5,
  "status": "running"
}
