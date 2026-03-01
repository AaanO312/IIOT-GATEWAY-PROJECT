# Industrial IoT Edge Gateway (工业物联网边缘网关)


## Project Overview (项目简介)
This project is a full-stack Industrial IoT (IIoT) prototype designed to solve the latency and visibility issues in traditional manufacturing lines. It integrates **Edge Computing**, **Real-time Telemetry**, and **Closed-loop Control**.
本项目是一个全栈工业物联网原型，旨在解决传统产线数据滞后和缺乏可视化的问题。系统集成了边缘计算、实时遥测和闭环控制功能。


## Key Features (核心功能)
*   **Real-time Telemetry (实时遥测)**: Replaced HTTP with **MQTT protocol** to achieve millisecond-level data synchronization.
*   **Edge Computing (边缘计算)**: Implemented local **State Machine** for signal debouncing and **Closed-loop Control** (Temp -> Relay) to ensure safety.
*   **Data Persistence (数据持久化)**: Integrated **SQLite** to ensure zero data loss during power outages.
*   **Visualization (可视化)**: Dynamic Dashboard built with **ECharts** & **WebSocket**.


## Tech Stack (技术栈)
*   **Hardware**: ESP32, OLED, Arcade Button, WS2812 LEDs, Relay, Potentiometer.
*   **Firmware**: C++ / PlatformIO.
*   **Backend**: Python Flask / Socket.IO / Paho-MQTT.
*   **Database**: SQLite.


## Hardware Wiring (硬件接线)
| Component | Pin | ESP32 GPIO | Function |
| :--- | :--- | :--- | :--- |
| **Button** | Signal | GPIO 14 | Production Counter |
| **OLED** | SDA/SCL | GPIO 21/22 | Status Display |
| **LED Ring** | DIN | GPIO 27 | Visual Alarm |
| **Potentiometer**| OUT | GPIO 34 | Temp Simulation (ADC) |
| **Relay** | IN | GPIO 26 | Fan Control (Output) |


## How to Run (运行指南)
1.  Connect ESP32 to power.
2.  Start Backend: `python app.py`
3.  Open Browser: `http://localhost:5000`
