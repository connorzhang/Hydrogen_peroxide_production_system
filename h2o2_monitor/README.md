# 双氧水生产系统 - 上位机监控软件

本项目为双氧水生产系统量身定制的轻量级、原生桌面监控软件，采用 **Rust + Slint + Modbus TCP** 架构。

## 特点
- **极简单文件发布**：编译后仅生成一个体积几MB的 `.exe` 文件，无需在工控机上安装任何运行时环境（Python/Node.js等）。
- **极低资源占用**：原生编译，内存占用极小，适合长期在工控机上全屏稳定运行。
- **工业级 UI**：基于 Slint 声明式 UI 编写，呈现暗黑工业风大屏监控界面。
- **毫秒级刷新**：使用以太网 Modbus TCP 异步轮询 PLC，数据无感延迟。

## 开发与编译环境准备

在另外一台开发电脑上，需要准备以下环境：
1. **安装 Rust**：前往 [Rust 官网](https://rustup.rs/) 下载 `rustup-init.exe` 并默认安装。
2. **安装 C++ 编译工具链**：下载安装 **Visual Studio Build Tools**，并在安装时勾选 **“使用 C++ 的桌面开发”** (MSVC Linker，Rust 编译 Windows 原生程序必需)。

## 编译指南

1. 同步此代码仓库后，进入上位机目录：
   ```bash
   cd h2o2_monitor
   ```
2. 运行 Release 模式编译：
   ```bash
   cargo build --release
   ```
3. 编译完成后，在 `target/release/` 目录下会生成 `h2o2_monitor.exe`。
4. **部署**：将该 `.exe` 文件直接拷贝到车间工控机上，双击运行即可。

## PLC 端配合设置 (S7-200 SMART)

上位机通过 **Modbus TCP** 读取 PLC 数据，请在 PLC 程序 (`OB1`) 中做如下极简配置：
1. 调出 `MBUS_SERVER` (Modbus TCP 服务器) 指令。
2. 配置参数：
   - **MaxIQ / MaxAI / MaxAQ**：`0`
   - **HoldStart**：`&VB2000` (将 V 区 2000 开始的地址映射给 4xxxx 保持寄存器)
   - **MaxHold**：`1000`
3. 确保 PLC 设定了静态 IP（代码默认指向 `192.168.2.1:502`，如不同请在 `src/main.rs` 中修改）。

## 项目结构
- `ui/app.slint`：界面布局与样式文件，修改此文件可改变页面颜色、文字、指示灯及绑定属性。
- `src/main.rs`：后端 Rust 逻辑，负责启动异步 Modbus TCP 连接并把读取到的数据映射到 UI。
- `build.rs`：编译脚本，在编译时将 `.slint` 文件转化为 Rust 机器码。
