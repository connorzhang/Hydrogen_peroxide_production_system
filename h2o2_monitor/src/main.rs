slint::include_modules!();

use std::time::Duration;
use tokio::time::sleep;
use tokio_modbus::prelude::*;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. 初始化 Slint UI 窗口
    let ui = AppWindow::new()?;
    let ui_handle = ui.as_weak();

    // 2. 启动后台 Modbus TCP 轮询任务
    // 假设 PLC 的 IP 是 192.168.2.1，端口 502
    // 如果现场 IP 不同，请在此修改
    let plc_addr = "192.168.2.1:502".parse().unwrap();
    
    tokio::spawn(async move {
        println!("Connecting to PLC at {}...", plc_addr);
        
        // 不断重连机制
        loop {
            match tcp::connect(plc_addr).await {
                Ok(mut ctx) => {
                    println!("Connected to PLC!");
                    
                    // 循环读取数据
                    loop {
                        // 读取 V 区数据 (映射到 4xxxx 保持寄存器)
                        // 根据你的 V区表，我们假设从 VB2000 开始映射 (地址0)
                        // VD2100 (压力) -> 偏移 50 字 (100字节) -> 地址 50, 长度 2 (Real)
                        // VD2104 (阳极液位) -> 地址 52, 长度 2
                        // VD2108 (阴极液位) -> 地址 54, 长度 2
                        // VD1310 (阳极流量) -> 我们需要在 PLC 里把 VD1310 也搬到 V2000 区域，比如 VD2200
                        // 暂且用模拟数据更新 UI
                        
                        // 真实读取代码示例：
                        // if let Ok(data) = ctx.read_holding_registers(50, 2).await { ... }

                        let ui_handle_clone = ui_handle.clone();
                        slint::invoke_from_event_loop(move || {
                            if let Some(ui) = ui_handle_clone.upgrade() {
                                // 这里填入解析后的真实数据，这里暂时写死做演示
                                // ui.set_pressure_mpa(read_real(&data));
                            }
                        }).unwrap();

                        sleep(Duration::from_millis(500)).await;
                    }
                }
                Err(e) => {
                    eprintln!("Connection failed: {}. Retrying in 3s...", e);
                    sleep(Duration::from_secs(3)).await;
                }
            }
        }
    });

    // 3. 运行 UI 阻塞主线程
    ui.run()?;
    Ok(())
}
