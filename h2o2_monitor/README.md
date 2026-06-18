# 双氧水生产系统 - 上位机监控软件

本项目为双氧水生产系统的独立原生桌面监控前端，采用 **Rust + Slint + S7 TCP 直连 PLC** 架构。

## 数据来源

上位机直接连接 S7-200 SMART PLC，不依赖 Flask 网页监控服务。

默认 PLC 地址：

```text
192.168.1.11:102
```

可通过环境变量覆盖：

```powershell
$env:H2O2_PLC_ADDR="192.168.1.11:102"
cargo run
```

## 当前接入字段

| UI 内容 | PLC 地址/来源 |
|---|---|
| PLC 连接状态 | S7 TCP 连接状态 |
| 当前流程 | `VB100` / `VB101` |
| 制水机 | `Q1.0` |
| 空压机 | `Q1.1` |
| 阳极补水阀 | `Q0.0` |
| 阴极补水阀 | `Q0.1` |
| 阳极电磁阀 | `Q0.2` |
| 阴极电磁阀 | `Q0.3` |
| 直流电源 | `Q1.2` |
| 阳极泵 | `M1.0` |
| 阴极泵 | `M1.1` |
| 压力达标 | `V2303.0` |
| 阳极低液位报警 | `V2303.1` |
| 阴极低液位报警 | `V2303.2` |
| 阳极流量达标 | `V2303.3` |
| 阴极流量达标 | `V2303.4` |
| 生产缺流报警 | `V2303.5` |
| 综合报警 | `V2303.1` / `V2303.2` / `V2303.5` |
| 高压罐压力 | `VD2100`，单位 kPa |
| 阳极液位 | `VD2112`，单位 cm |
| 阴极液位 | `VD2116`，单位 cm |
| 阳极流量 | `VD1310`，单位 L/min |
| 阴极流量 | `VD1330`，单位 L/min |
| 阳极泵输出 | `VW2020` / `M1.0`，按 0~10V 显示 |
| 阴极泵输出 | `VW2026` / `M1.1`，按 0~10V 显示 |

## 特点

- 原生桌面 UI：基于 Slint 声明式 UI 编写。
- 独立直连 PLC：不依赖 Python、Flask 或网页服务。
- 统一现场口径：读取地址与 `h2o2_final.awl` 当前稳定版一致。
- 可配置 PLC 地址：通过 `H2O2_PLC_ADDR` 切换 PLC IP。

## 编译指南

### Windows 编译环境

Windows 上当前项目使用 `x86_64-pc-windows-msvc` 工具链，需要先安装：

- Rust stable 工具链。
- Visual Studio Build Tools 2019/2022/2026。
- `Desktop development with C++` 工作负载。
- MSVC C++ Build Tools。
- Windows 10/11 SDK。

安装完成后重新打开终端，确认以下命令可用：

```powershell
rustc --version
cargo --version
cl
link
```

如果 Cargo 源访问失败，可在用户目录 `C:\Users\<用户名>\.cargo\config.toml` 配置 sparse 镜像：

```toml
[source.crates-io]
replace-with = "rsproxy"

[source.rsproxy]
registry = "sparse+https://rsproxy.cn/index/"

[net]
git-fetch-with-cli = true
```

### 运行前注意

S7-200 SMART 的 S7 TCP 连接数有限，正式运行时只能保留一个 PLC 通信主站。运行本程序前应关闭：

- `plc_dashboard.py` 网页调试服务。
- Micro/WIN SMART 在线监控。
- 其它 Snap7/S7 TCP 调试工具。

刷 PLC 程序前也需要退出本上位机，避免占用 PLC 通信连接。

### 编译运行

1. 进入上位机目录：

```bash
cd h2o2_monitor
```

2. 开发运行：

```bash
cargo run
```

3. Release 编译：

```bash
cargo build --release
```

编译完成后，在 `target/release/` 目录下生成 `h2o2_monitor.exe`。

## 项目结构

- `ui/app.slint`：界面布局、状态灯、液位罐和数值大屏。
- `src/main.rs`：S7 TCP 连接、PLC 数据读取和 Slint 属性映射。
- `build.rs`：编译脚本，在编译时将 `.slint` 文件转化为 Rust 代码。
