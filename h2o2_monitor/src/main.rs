slint::include_modules!();

use std::io::{Read, Write};
use std::net::TcpStream;
use std::sync::{Arc, RwLock};
use std::time::Duration;
use tokio::time::sleep;

const AREA_PE: u8 = 0x81;
const AREA_PA: u8 = 0x82;
const AREA_MK: u8 = 0x83;
const AREA_DB: u8 = 0x84;

#[allow(dead_code)]
#[derive(Clone, Copy, Debug, Default)]
struct PlcData {
    connected: bool,
    i_flow_anode: bool,
    i_start: bool,
    i_stop: bool,
    i_emergency: bool,
    i_flow_cathode: bool,
    q_refill_anode: bool,
    q_refill_cathode: bool,
    q_valve_anode: bool,
    q_valve_cathode: bool,
    q_water_maker: bool,
    q_air_compressor: bool,
    q_dc_power: bool,
    pump_anode_enable: bool,
    pump_cathode_enable: bool,
    shutdown_delay: bool,
    pressure_ready: bool,
    anode_low_level_alarm: bool,
    cathode_low_level_alarm: bool,
    anode_flow_ready: bool,
    cathode_flow_ready: bool,
    flow_alarm: bool,
    pressure_anode: f32,
    pressure_cathode: f32,
    pressure_kpa: f32,
    level_anode: f32,
    level_cathode: f32,
    flow_anode: f32,
    flow_cathode: f32,
    sequence_startup: u8,
    sequence_shutdown: u8,
    anode_pwm_raw: u16,
    cathode_pwm_raw: u16,
    aqw32: u16,
    aqw34: u16,
    anode_flow_coeff: f32,
    cathode_flow_coeff: f32,
    pressure_target: f32,
    level_target: f32,
    sys_alarm: bool,
}

struct S7Client {
    stream: TcpStream,
    pdu_ref: u16,
}

impl S7Client {
    fn connect(addr: &str) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let remote_tsaps = [0x0301_u16, 0x0101_u16, 0x0201_u16, 0x0100_u16];
        let mut last_error = None;

        for remote_tsap in remote_tsaps {
            match Self::connect_with_tsap(addr, remote_tsap) {
                Ok(client) => return Ok(client),
                Err(error) => last_error = Some(error.to_string()),
            }
        }

        Err(last_error.unwrap_or_else(|| "connect failed".to_string()).into())
    }

    fn connect_with_tsap(addr: &str, remote_tsap: u16) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let mut stream = TcpStream::connect(addr)?;
        stream.set_read_timeout(Some(Duration::from_secs(2)))?;
        stream.set_write_timeout(Some(Duration::from_secs(2)))?;

        let local_tsap = 0x0100_u16;
        let cr = vec![
            0x03, 0x00, 0x00, 0x16,
            0x11, 0xe0, 0x00, 0x00, 0x00, 0x01, 0x00,
            0xc1, 0x02, (local_tsap >> 8) as u8, local_tsap as u8,
            0xc2, 0x02, (remote_tsap >> 8) as u8, remote_tsap as u8,
            0xc0, 0x01, 0x0a,
        ];
        stream.write_all(&cr)?;
        let _ = read_packet(&mut stream)?;

        let setup = vec![
            0x03, 0x00, 0x00, 0x19,
            0x02, 0xf0, 0x80,
            0x32, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x00, 0x08, 0x00, 0x00,
            0xf0, 0x00, 0x00, 0x01, 0x00, 0x01, 0x01, 0xe0,
        ];
        stream.write_all(&setup)?;
        let _ = read_packet(&mut stream)?;

        Ok(Self { stream, pdu_ref: 2 })
    }

    fn read_area(&mut self, area: u8, db: u16, start: u32, size: u16) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
        let pdu_ref = self.pdu_ref;
        self.pdu_ref = self.pdu_ref.wrapping_add(1);
        let bit_address = start * 8;
        let packet_len = 31_u16;
        let mut packet = vec![
            0x03, 0x00, (packet_len >> 8) as u8, packet_len as u8,
            0x02, 0xf0, 0x80,
            0x32, 0x01, 0x00, 0x00, (pdu_ref >> 8) as u8, pdu_ref as u8,
            0x00, 0x0e, 0x00, 0x00,
            0x04, 0x01,
            0x12, 0x0a, 0x10, 0x02,
            (size >> 8) as u8, size as u8,
            (db >> 8) as u8, db as u8,
            area,
            ((bit_address >> 16) & 0xff) as u8,
            ((bit_address >> 8) & 0xff) as u8,
            (bit_address & 0xff) as u8,
        ];

        self.stream.write_all(&packet)?;
        packet.clear();
        let response = read_packet(&mut self.stream)?;
        parse_read_response(&response, size as usize)
    }
}

fn read_packet(stream: &mut TcpStream) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
    let mut header = [0_u8; 4];
    stream.read_exact(&mut header)?;
    if header[0] != 0x03 {
        return Err("invalid TPKT header".into());
    }
    let length = u16::from_be_bytes([header[2], header[3]]) as usize;
    if length < 4 {
        return Err("invalid TPKT length".into());
    }
    let mut packet = vec![0_u8; length];
    packet[..4].copy_from_slice(&header);
    stream.read_exact(&mut packet[4..])?;
    Ok(packet)
}

fn parse_read_response(response: &[u8], size: usize) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
    if response.len() < 25 {
        return Err("short S7 response".into());
    }

    let s7_start = 7;
    if response.get(s7_start) != Some(&0x32) {
        return Err("invalid S7 response".into());
    }

    let rosctr = response[s7_start + 1];
    let header_len = if rosctr == 0x03 { 12 } else { 10 };
    let param_len = u16::from_be_bytes([response[s7_start + 6], response[s7_start + 7]]) as usize;
    let data_start = s7_start + header_len + param_len;
    if response.len() < data_start + 4 + size {
        return Err("short S7 data".into());
    }
    if response[data_start] != 0xff {
        return Err("S7 read failed".into());
    }

    Ok(response[data_start + 4..data_start + 4 + size].to_vec())
}

fn be_f32(data: &[u8], offset: usize) -> f32 {
    f32::from_bits(u32::from_be_bytes([
        data[offset],
        data[offset + 1],
        data[offset + 2],
        data[offset + 3],
    ]))
}

fn be_u16(data: &[u8], offset: usize) -> u16 {
    u16::from_be_bytes([data[offset], data[offset + 1]])
}

fn read_plc_data(client: &mut S7Client) -> Result<PlcData, Box<dyn std::error::Error + Send + Sync>> {
    let inp0 = client.read_area(AREA_PE, 0, 0, 1)?[0];
    let out0 = client.read_area(AREA_PA, 0, 0, 1)?[0];
    let out1 = client.read_area(AREA_PA, 0, 1, 1)?[0];
    let m1 = client.read_area(AREA_MK, 0, 1, 1)?[0];
    let m10 = client.read_area(AREA_MK, 0, 10, 1)?[0];
    let seq = client.read_area(AREA_DB, 1, 100, 2)?;
    let params_a = client.read_area(AREA_DB, 1, 2000, 32)?;
    let analog = client.read_area(AREA_DB, 1, 2100, 20)?;
    let flow = client.read_area(AREA_DB, 1, 1310, 24)?;
    let flags = client.read_area(AREA_DB, 1, 2303, 1)?[0];
    let vw2020 = be_u16(&params_a, 20);
    let vw2026 = be_u16(&params_a, 26);
    let aqw32 = if m1 & 0x01 != 0 { vw2020 } else { 0 };
    let aqw34 = if m1 & 0x02 != 0 { vw2026 } else { 0 };

    Ok(PlcData {
        connected: true,
        i_flow_anode: inp0 & 0x01 != 0,
        i_start: inp0 & 0x02 != 0,
        i_stop: inp0 & 0x04 != 0,
        i_emergency: inp0 & 0x08 != 0,
        i_flow_cathode: inp0 & 0x40 != 0,
        q_refill_anode: out0 & 0x01 != 0,
        q_refill_cathode: out0 & 0x02 != 0,
        q_valve_anode: out0 & 0x04 != 0,
        q_valve_cathode: out0 & 0x08 != 0,
        q_water_maker: out1 & 0x01 != 0,
        q_air_compressor: out1 & 0x02 != 0,
        q_dc_power: out1 & 0x04 != 0,
        pump_anode_enable: m1 & 0x01 != 0,
        pump_cathode_enable: m1 & 0x02 != 0,
        shutdown_delay: m10 & 0x02 != 0,
        pressure_ready: flags & 0x01 != 0,
        anode_low_level_alarm: flags & 0x02 != 0,
        cathode_low_level_alarm: flags & 0x04 != 0,
        anode_flow_ready: flags & 0x08 != 0,
        cathode_flow_ready: flags & 0x10 != 0,
        flow_alarm: flags & 0x20 != 0,
        pressure_kpa: be_f32(&analog, 0),
        pressure_anode: be_f32(&analog, 4),
        pressure_cathode: be_f32(&analog, 8),
        level_anode: be_f32(&analog, 12),
        level_cathode: be_f32(&analog, 16),
        flow_anode: be_f32(&flow, 0),
        flow_cathode: be_f32(&flow, 20),
        sequence_startup: seq[0],
        sequence_shutdown: seq[1],
        anode_pwm_raw: vw2020,
        cathode_pwm_raw: vw2026,
        aqw32,
        aqw34,
        pressure_target: be_f32(&params_a, 0),
        level_target: be_f32(&params_a, 12),
        anode_flow_coeff: be_f32(&params_a, 16),
        cathode_flow_coeff: be_f32(&params_a, 28),
        sys_alarm: flags & 0x02 != 0 || flags & 0x04 != 0 || flags & 0x20 != 0,
    })
}

fn apply_plc_data(ui: &AppWindow, data: PlcData) {
    ui.set_plc_connected(data.connected);

    if !data.connected {
        ui.set_q_water_maker(false);
        ui.set_q_air_compressor(false);
        ui.set_q_valve_anode(false);
        ui.set_q_valve_cathode(false);
        ui.set_q_dc_power(false);
        ui.set_sys_alarm(true);
        return;
    }

    ui.set_q_valve_anode(data.q_valve_anode);
    ui.set_q_valve_cathode(data.q_valve_cathode);
    ui.set_q_water_maker(data.q_water_maker);
    ui.set_q_air_compressor(data.q_air_compressor);
    ui.set_q_dc_power(data.q_dc_power);
    ui.set_q_refill_anode(data.q_refill_anode);
    ui.set_q_refill_cathode(data.q_refill_cathode);
    ui.set_pump_anode_enable(data.pump_anode_enable);
    ui.set_pump_cathode_enable(data.pump_cathode_enable);
    ui.set_pressure_ready(data.pressure_ready);
    ui.set_anode_low_level_alarm(data.anode_low_level_alarm);
    ui.set_cathode_low_level_alarm(data.cathode_low_level_alarm);
    ui.set_anode_flow_ready(data.anode_flow_ready);
    ui.set_cathode_flow_ready(data.cathode_flow_ready);
    ui.set_flow_alarm(data.flow_alarm);
    ui.set_pressure_kpa(data.pressure_kpa);
    ui.set_level_anode(data.level_anode);
    ui.set_level_cathode(data.level_cathode);
    ui.set_level_anode_ratio((data.level_anode / 60.0).clamp(0.0, 1.0));
    ui.set_level_cathode_ratio((data.level_cathode / 60.0).clamp(0.0, 1.0));
    ui.set_flow_anode(data.flow_anode);
    ui.set_flow_cathode(data.flow_cathode);
    ui.set_sequence_text(sequence_text(data.sequence_startup, data.sequence_shutdown).into());
    ui.set_pump_anode_voltage(data.aqw32 as f32 / 27648.0 * 10.0);
    ui.set_pump_cathode_voltage(data.aqw34 as f32 / 27648.0 * 10.0);
    ui.set_sys_alarm(data.sys_alarm);
}

fn sequence_text(startup: u8, shutdown: u8) -> &'static str {
    if shutdown == 10 {
        return "关机：停止直流/阴极";
    }
    if shutdown == 20 {
        return "关机：阳极延时";
    }
    match startup {
        0 => "待机",
        10 => "补水升压",
        20 => "阳极运行",
        30 => "阴阳极运行",
        _ => "未知步骤",
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let ui = AppWindow::new()?;
    let ui_handle = ui.as_weak();
    let plc_addr = std::env::var("H2O2_PLC_ADDR").unwrap_or_else(|_| "192.168.1.11:102".to_string());
    let latest_data = Arc::new(RwLock::new(PlcData::default()));
    let collector_data = latest_data.clone();

    tokio::spawn(async move {
        loop {
            match S7Client::connect(&plc_addr) {
                Ok(mut client) => loop {
                    match read_plc_data(&mut client) {
                        Ok(data) => {
                            if let Ok(mut latest) = collector_data.write() {
                                *latest = data;
                            }
                            let ui_handle_clone = ui_handle.clone();
                            let _ = slint::invoke_from_event_loop(move || {
                                if let Some(ui) = ui_handle_clone.upgrade() {
                                    apply_plc_data(&ui, data);
                                }
                            });
                        }
                        Err(error) => {
                            eprintln!("PLC read failed: {}", error);
                            if let Ok(mut latest) = collector_data.write() {
                                latest.connected = false;
                                latest.sys_alarm = true;
                            }
                            let ui_handle_clone = ui_handle.clone();
                            let _ = slint::invoke_from_event_loop(move || {
                                if let Some(ui) = ui_handle_clone.upgrade() {
                                    ui.set_plc_connected(false);
                                    ui.set_sys_alarm(true);
                                }
                            });
                            break;
                        }
                    }

                    sleep(Duration::from_millis(500)).await;
                },
                Err(error) => {
                    eprintln!("PLC connect failed: {}", error);
                    if let Ok(mut latest) = collector_data.write() {
                        latest.connected = false;
                        latest.sys_alarm = true;
                    }
                    let ui_handle_clone = ui_handle.clone();
                    let _ = slint::invoke_from_event_loop(move || {
                        if let Some(ui) = ui_handle_clone.upgrade() {
                            ui.set_plc_connected(false);
                            ui.set_sys_alarm(true);
                        }
                    });
                    sleep(Duration::from_secs(3)).await;
                }
            }
        }
    });

    ui.run()?;
    Ok(())
}
