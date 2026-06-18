from flask import Flask, jsonify, render_template_string, request
import snap7
from snap7 import Area
from snap7.util import get_word
import struct
import threading
import time

app = Flask(__name__)

plc_data = {
    'connected': False,
    'inputs': {},
    'outputs': {},
    'analog_raw': {},
    'pressure': {},
    'level': {},
    'flow': {},
    'flow_rate': {},
    'sequence': {},
    'flags': {},
    'level_control': {},
    'timestamp': ''
}

# Shared PLC client and lock
plc_client = snap7.client.Client()
plc_client.set_connection_type(3)
plc_lock = threading.Lock()

def plc_connect():
    if not plc_client.get_connected():
        plc_client.connect('192.168.1.11', 0, 1)

def read_plc():
    global plc_data
    
    while True:
        try:
            with plc_lock:
                plc_connect()
                inp = plc_client.read_area(Area.PE, 0, 0, 1)
                out0 = plc_client.read_area(Area.PA, 0, 0, 1)
                out1 = plc_client.read_area(Area.PA, 0, 1, 1)

                # Raw AIW values from VW area (per corrected I/O mapping)
                # VW1000=AIW16(CH0), VW1002=AIW18(CH1), VW1004=AIW20(CH2)
                # VW1010=AIW22(CH3), VW1012=AIW24(CH4), VW1014=AIW26(CH5)
                # VW1016=AIW28(CH6), VW1018=AIW30(CH7)
                aiw16 = get_word(plc_client.db_read(1, 1000, 2), 0)  # CH0
                aiw18 = get_word(plc_client.db_read(1, 1002, 2), 0)  # CH1
                aiw20 = get_word(plc_client.db_read(1, 1004, 2), 0)  # CH2
                aiw22 = get_word(plc_client.db_read(1, 1010, 2), 0)  # CH3
                aiw24 = get_word(plc_client.db_read(1, 1012, 2), 0)  # CH4
                aiw26 = get_word(plc_client.db_read(1, 1014, 2), 0)  # CH5
                aiw28 = get_word(plc_client.db_read(1, 1016, 2), 0)  # CH6
                aiw30 = get_word(plc_client.db_read(1, 1018, 2), 0)  # CH7

                # Float values from VD2100+
                vd2100 = struct.unpack('>f', plc_client.db_read(1, 2100, 4))[0]  # 高压罐压力
                vd2104 = struct.unpack('>f', plc_client.db_read(1, 2104, 4))[0]  # 阳极压力
                vd2108 = struct.unpack('>f', plc_client.db_read(1, 2108, 4))[0]  # 阴极压力
                vd2112 = struct.unpack('>f', plc_client.db_read(1, 2112, 4))[0]  # 阳极液位
                vd2116 = struct.unpack('>f', plc_client.db_read(1, 2116, 4))[0]  # 阴极液位

                vd1200 = struct.unpack('>i', plc_client.db_read(1, 1200, 4))[0]
                vd1208 = struct.unpack('>i', plc_client.db_read(1, 1208, 4))[0]
                vd1220 = struct.unpack('>i', plc_client.db_read(1, 1220, 4))[0]
                vd1228 = struct.unpack('>i', plc_client.db_read(1, 1228, 4))[0]
                vd1310 = struct.unpack('>f', plc_client.db_read(1, 1310, 4))[0]
                vd1330 = struct.unpack('>f', plc_client.db_read(1, 1330, 4))[0]
                ctu0 = get_word(plc_client.db_read(1, 1360, 2), 0)  # CTU C0 diagnostic
                ctu1 = get_word(plc_client.db_read(1, 1362, 2), 0)  # CTU C1 diagnostic
                hc1_diag = struct.unpack('>i', plc_client.db_read(1, 1404, 4))[0]
                hc2_diag = struct.unpack('>i', plc_client.db_read(1, 1408, 4))[0]
                hc3_diag = struct.unpack('>i', plc_client.db_read(1, 1412, 4))[0]
                hc4_diag = struct.unpack('>i', plc_client.db_read(1, 1416, 4))[0]
                hc5_diag = struct.unpack('>i', plc_client.db_read(1, 1420, 4))[0]

                vb100 = plc_client.db_read(1, 100, 1)[0]
                vb101 = plc_client.db_read(1, 101, 1)[0]
                m1 = plc_client.read_area(Area.MK, 0, 1, 1)[0]
                m10 = plc_client.read_area(Area.MK, 0, 10, 1)[0]
                v2302 = plc_client.db_read(1, 2302, 1)[0]
                v2303 = plc_client.db_read(1, 2303, 1)[0]

                # Configurable parameters
                vd2000 = struct.unpack('>f', plc_client.db_read(1, 2000, 4))[0]  # pressure target
                vd2012 = struct.unpack('>f', plc_client.db_read(1, 2012, 4))[0]  # level target
                vd2016 = struct.unpack('>f', plc_client.db_read(1, 2016, 4))[0]  # anode flow coefficient
                vd2028 = struct.unpack('>f', plc_client.db_read(1, 2028, 4))[0]  # cathode flow coefficient
                vw2024 = get_word(plc_client.db_read(1, 2024, 2), 0)  # step delay
                vw2020 = get_word(plc_client.db_read(1, 2020, 2), 0)  # anode PWM duty cycle
                vw2026 = get_word(plc_client.db_read(1, 2026, 2), 0)  # cathode PWM duty cycle
                # Calculate actual pump outputs from enable flags
                aqw32 = vw2020 if (m1 & 0x01) else 0  # M1.0 = anode pump
                aqw34 = vw2026 if (m1 & 0x02) else 0  # M1.1 = cathode pump

            plc_data = {
                'connected': True,
                'inputs': {
                    'I0.0': bool(inp[0] & 0x01),
                    'I0.1': bool(inp[0] & 0x02),
                    'I0.2': bool(inp[0] & 0x04),
                    'I0.3': bool(inp[0] & 0x08),
                    'I0.6': bool(inp[0] & 0x40),
                },
                'outputs': {
                    'Q0.0': bool(out0[0] & 0x01),
                    'Q0.1': bool(out0[0] & 0x02),
                    'Q0.2': bool(out0[0] & 0x04),
                    'Q0.3': bool(out0[0] & 0x08),
                    'Q1.0': bool(out1[0] & 0x01),
                    'Q1.1': bool(out1[0] & 0x02),
                    'Q1.2': bool(out1[0] & 0x04),
                },
                'analog_raw': {
                    'AIW16(CH0)': aiw16, 'AIW18(CH1)': aiw18, 'AIW20(CH2)': aiw20,
                    'AIW22(CH3)': aiw22, 'AIW24(CH4)': aiw24, 'AIW26(CH5)': aiw26,
                    'AIW28(CH6)': aiw28, 'AIW30(CH7)': aiw30
                },
                'pressure': {
                    'high_tank': round(vd2100, 1),
                    'anode': round(vd2104, 1),
                    'cathode': round(vd2108, 1)
                },
                'level': {
                    'anode': round(vd2112, 1),
                    'cathode': round(vd2116, 1)
                },
                'flow': {
                    'HC0': vd1200, 'CTU1_FLOW': vd1220,
                    'pps1': vd1208, 'pps2': vd1228,
                    'CTU0': ctu0, 'CTU1': ctu1
                },
                'hsc_diag': {
                    'HC1': hc1_diag, 'HC2': hc2_diag, 'HC3': hc3_diag,
                    'HC4': hc4_diag, 'HC5': hc5_diag
                },
                'flow_rate': {
                    'flow1': round(vd1310, 3),
                    'flow2': round(vd1330, 3)
                },
                'sequence': {
                    'VB100': vb100, 'VB101': vb101
                },
                'flags': {
                    'M1.0': bool(m1 & 0x01),
                    'M1.1': bool(m1 & 0x02),
                    'M10.1': bool(m10 & 0x02),
                    'V2303.0': bool(v2303 & 0x01),
                    'V2303.1': bool(v2303 & 0x02),
                    'V2303.2': bool(v2303 & 0x04),
                    'V2303.3': bool(v2303 & 0x08),
                    'V2303.4': bool(v2303 & 0x10),
                    'V2303.5': bool(v2303 & 0x20),
                },
                'level_control': {
                    'anode_refill_on': 45.0,
                    'cathode_refill_on': 45.0,
                    'refill_off': round(vd2012, 1),
                    'low_alarm': 20.0
                },
                'params': {
                    'pressure_target': round(vd2000, 1),
                    'level_target': round(vd2012, 1),
                    'anode_flow_coeff': round(vd2016, 1),
                    'cathode_flow_coeff': round(vd2028, 1),
                    'step_delay': vw2024
                },
                'pumps': {
                    'anode_pwm_raw': vw2020,
                    'cathode_pwm_raw': vw2026,
                    'aqw32': aqw32,
                    'aqw34': aqw34
                },
                'timestamp': time.strftime('%H:%M:%S')
            }
        except Exception as e:
            plc_data['connected'] = False
            plc_data['error'] = str(e)
        
        time.sleep(0.5)

@app.route('/api/control', methods=['POST'])
def control():
    action = request.json.get('action')
    try:
        with plc_lock:
            plc_connect()
            current = plc_client.db_read(1, 2302, 1)[0]
            bit_map = {
                'start': 0x01,
                'stop': 0x02,
                'emergency': 0x04,
                'compressor_on': 0x08,
                'compressor_off': 0x10,
            }
            mask = bit_map.get(action, 0)
            if mask:
                new_val = current | mask
                plc_client.db_write(1, 2302, bytearray([new_val]))
                return jsonify({'ok': True, 'wrote': new_val})
            return jsonify({'ok': True, 'wrote': current})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/set_param', methods=['POST'])
def set_param():
    name = request.json.get('name')
    value = request.json.get('value')
    try:
        with plc_lock:
            plc_connect()
            if name == 'level_target':
                plc_client.db_write(1, 2012, bytearray(struct.pack('>f', float(value))))
            elif name == 'pressure_target':
                plc_client.db_write(1, 2000, bytearray(struct.pack('>f', float(value))))
            elif name == 'step_delay':
                plc_client.db_write(1, 2024, struct.pack('>H', int(value)))
            elif name == 'cathode_pump_voltage':
                voltage = max(0.0, min(10.0, float(value)))
                raw = max(0, min(27648, int(round(voltage / 10.0 * 27648))))
                plc_client.db_write(1, 2026, struct.pack('>H', raw))
            return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>双氧水生产 - PLC实时监测</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
h1 { text-align: center; color: #38bdf8; margin-bottom: 20px; font-size: 24px; }
.status-bar { text-align: center; padding: 8px; margin-bottom: 20px; border-radius: 8px; font-weight: bold; font-size: 14px; }
.status-bar.online { background: #064e3b; color: #34d399; }
.status-bar.offline { background: #7f1d1d; color: #fca5a5; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.card { background: #1e293b; border-radius: 12px; padding: 16px; border: 1px solid #334155; }
.card h2 { color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #334155; }
.row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #1e293b33; }
.row:last-child { border-bottom: none; }
.label { color: #94a3b8; font-size: 13px; }
.value { font-size: 14px; font-weight: 600; font-family: 'Consolas', monospace; }
.on { color: #34d399; }
.off { color: #64748b; }
.highlight { color: #fbbf24; }
.seq-active { background: #1e3a5f; border-radius: 6px; padding: 4px 8px; }
.timestamp { text-align: center; color: #64748b; font-size: 12px; margin-top: 16px; }
.control-panel { background: #1e293b; border-radius: 12px; padding: 16px; border: 1px solid #334155; margin-bottom: 16px; }
.control-panel h2 { color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #334155; }
.btn-row { display: flex; gap: 12px; flex-wrap: wrap; }
.btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s; color: white; }
.btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
.btn:active { transform: translateY(0); }
.btn-start { background: #059669; }
.btn-start:hover { background: #047857; }
.btn-stop { background: #d97706; }
.btn-stop:hover { background: #b45309; }
.btn-emergency { background: #dc2626; }
.btn-emergency:hover { background: #b91c1c; }
.btn-compressor-on { background: #2563eb; }
.btn-compressor-on:hover { background: #1d4ed8; }
.btn-compressor-off { background: #64748b; }
.btn-compressor-off:hover { background: #475569; }
.overview-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.metric { background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 12px; }
.metric-title { color: #94a3b8; font-size: 12px; margin-bottom: 8px; }
.metric-value { font-size: 22px; font-weight: 700; color: #e2e8f0; font-family: 'Consolas', monospace; }
.metric-sub { color: #64748b; font-size: 12px; margin-top: 6px; }
.process-list { display: flex; flex-direction: column; gap: 10px; }
.process-step { display: grid; grid-template-columns: 34px 1fr auto; gap: 12px; align-items: center; background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 12px; }
.process-index { width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: #334155; color: #94a3b8; font-weight: 700; }
.process-title { font-size: 15px; font-weight: 700; color: #e2e8f0; }
.process-desc { color: #94a3b8; font-size: 12px; margin-top: 4px; line-height: 1.5; }
.process-state { font-size: 12px; padding: 4px 10px; border-radius: 999px; background: #334155; color: #94a3b8; }
.process-step.active { border-color: #38bdf8; background: #082f49; }
.process-step.active .process-index { background: #0284c7; color: white; }
.process-step.active .process-state { background: #0284c7; color: white; }
.process-step.done { opacity: 0.78; }
.process-step.done .process-index { background: #047857; color: white; }
.process-step.alarm { border-color: #ef4444; background: #450a0a; }
.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.status-item { background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 10px 12px; }
.status-name { color: #94a3b8; font-size: 12px; margin-bottom: 6px; }
.status-text { font-size: 14px; font-weight: 700; }
.status-ok { color: #34d399; }
.status-warn { color: #fbbf24; }
.status-bad { color: #f87171; }
</style>
</head>
<body>
<h1>双氧水生产系统 - PLC实时监测</h1>
<div id="statusBar" class="status-bar offline">连接中...</div>
<div class="control-panel">
  <h2>控制面板</h2>
  <div class="btn-row">
    <button class="btn btn-start" onclick="sendControl('start')">开机</button>
    <button class="btn btn-stop" onclick="sendControl('stop')">关机</button>
    <button class="btn btn-emergency" onclick="sendControl('emergency')">急停</button>
    <button class="btn btn-compressor-on" onclick="sendControl('compressor_on')">空压机开</button>
    <button class="btn btn-compressor-off" onclick="sendControl('compressor_off')">空压机关</button>
  </div>
</div>
<div class="control-panel">
  <h2>参数设置</h2>
  <div class="btn-row" style="align-items:center; gap:16px;">
    <span style="color:#94a3b8; font-size:13px;">补水停止/开机液位(cm):</span>
    <input id="levelTarget" type="number" step="0.1" min="1" max="200" oninput="paramDirty['level_target']=true" style="width:80px; padding:6px 8px; border-radius:6px; border:1px solid #475569; background:#0f172a; color:#e2e8f0; font-size:14px;">
    <button class="btn btn-start" onclick="setParam('level_target')" style="padding:8px 16px; font-size:13px;">设置</button>
    <span style="color:#94a3b8; font-size:13px;">压力阈值(kPa):</span>
    <input id="pressureTarget" type="number" step="0.1" min="1" max="200" oninput="paramDirty['pressure_target']=true" style="width:80px; padding:6px 8px; border-radius:6px; border:1px solid #475569; background:#0f172a; color:#e2e8f0; font-size:14px;">
    <button class="btn btn-stop" onclick="setParam('pressure_target')" style="padding:8px 16px; font-size:13px;">设置</button>
    <span style="color:#94a3b8; font-size:13px;">阴极启动延时(×100ms):</span>
    <input id="stepDelay" type="number" step="1" min="1" max="30000" oninput="paramDirty['step_delay']=true" style="width:80px; padding:6px 8px; border-radius:6px; border:1px solid #475569; background:#0f172a; color:#e2e8f0; font-size:14px;">
    <button class="btn btn-compressor-on" onclick="setParam('step_delay')" style="padding:8px 16px; font-size:13px;">设置</button>
    <span style="color:#94a3b8; font-size:13px;">阴极泵电压(V):</span>
    <input id="cathodePumpVoltage" type="text" inputmode="decimal" oninput="paramDirty['cathode_pump_voltage']=true" style="width:80px; padding:6px 8px; border-radius:6px; border:1px solid #475569; background:#0f172a; color:#e2e8f0; font-size:14px;">
    <button class="btn btn-compressor-on" onclick="setParam('cathode_pump_voltage')" style="padding:8px 16px; font-size:13px;">设置</button>
  </div>
</div>
<div class="control-panel">
  <h2>现场总览</h2>
  <div id="overview" class="overview-grid"></div>
</div>
<div class="control-panel">
  <h2>顺序流程</h2>
  <div id="processList" class="process-list"></div>
</div>
<div class="control-panel">
  <h2>运行状态</h2>
  <div id="operationStatus" class="status-grid"></div>
</div>
<div class="grid">
  <div class="card">
    <h2>现场输入</h2>
    <div id="inputs"></div>
  </div>
  <div class="card">
    <h2>现场设备输出</h2>
    <div id="outputs"></div>
  </div>
  <div class="card">
    <h2>模拟量原始值</h2>
    <div id="analog"></div>
  </div>
  <div class="card">
    <h2>压力 (kPa)</h2>
    <div id="pressure"></div>
  </div>
  <div class="card">
    <h2>液位 (cm)</h2>
    <div id="level"></div>
  </div>
  <div class="card">
    <h2>液位控制阈值 (cm)</h2>
    <div id="levelControl"></div>
  </div>
  <div class="card">
    <h2>脉冲计数</h2>
    <div id="flow"></div>
  </div>
  <div class="card">
    <h2>HSC诊断</h2>
    <div id="hscDiag"></div>
  </div>
  <div class="card">
    <h2>瞬时流量 (L/min)</h2>
    <div id="flowrate"></div>
  </div>
  <div class="card">
    <h2>流程编号</h2>
    <div id="sequence"></div>
  </div>
  <div class="card">
    <h2>报警与联锁</h2>
    <div id="flags"></div>
  </div>
  <div class="card">
    <h2>泵输出 (PWM)</h2>
    <div id="pumps"></div>
  </div>
</div>
<div class="timestamp" id="timestamp"></div>

<script>
const inputLabels = {'I0.0':'阳极流量计','I0.1':'开机按钮','I0.2':'关机按钮','I0.3':'急停按钮','I0.6':'阴极流量计'};
const outputLabels = {'Q0.0':'阳极补水阀','Q0.1':'阴极补水阀','Q0.2':'阳极控制阀','Q0.3':'阴极液体阀','Q1.0':'纯水机','Q1.1':'空压机','Q1.2':'直流电源'};
const analogLabels = {'AIW16(CH0)':'CH0-高压罐压力','AIW18(CH1)':'CH1-阳极压力','AIW20(CH2)':'CH2-阴极压力','AIW22(CH3)':'CH3-阳极液位','AIW24(CH4)':'CH4-阴极液位','AIW26(CH5)':'CH5-预留','AIW28(CH6)':'CH6-预留','AIW30(CH7)':'CH7-预留'};
const pressureLabels = {'high_tank':'高压罐','anode':'阳极','cathode':'阴极'};
const levelLabels = {'anode':'阳极桶','cathode':'阴极桶'};
const flowLabels = {'HC0':'HSC0(阳极)','CTU1_FLOW':'CTU1流量计数(阴极-I0.6)','pps1':'脉冲/100ms(阳极)','pps2':'脉冲/100ms(阴极)','CTU0':'CTU诊断(阳极)','CTU1':'CTU诊断(阴极)'};
const hscDiagLabels = {'HC1':'HSC1','HC2':'HSC2','HC3':'HSC3','HC4':'HSC4','HC5':'HSC5'};
const flowRateLabels = {'flow1':'阳极流量','flow2':'阴极流量'};
const seqLabels = {'VB100':'开机步骤','VB101':'关机步骤'};
const flagLabels = {'M1.0':'阳极泵使能','M1.1':'阴极泵使能','M10.1':'关机延时','V2303.0':'压力达标','V2303.1':'阳极低液位报警','V2303.2':'阴极低液位报警','V2303.3':'阳极流量达标','V2303.4':'阴极流量达标','V2303.5':'生产缺流报警'};
const levelControlLabels = {'anode_refill_on':'阳极低于开启','cathode_refill_on':'阴极低于开启','refill_off':'达到关闭','low_alarm':'低液位报警'};

function renderBool(id, data, labels) {
  let html = '';
  for (let [k, v] of Object.entries(data)) {
    html += `<div class="row"><span class="label">${labels[k]||k}</span><span class="value ${v?'on':'off'}">${v?'ON':'OFF'}</span></div>`;
  }
  document.getElementById(id).innerHTML = html;
}

function renderValue(id, data, labels, unit) {
  let html = '';
  for (let [k, v] of Object.entries(data)) {
    let cls = v !== 0 && v !== 0.0 ? 'highlight' : '';
    html += `<div class="row"><span class="label">${labels[k]||k}</span><span class="value ${cls}">${v}${unit?' '+unit:''}</span></div>`;
  }
  document.getElementById(id).innerHTML = html;
}

function fmt(v, digits=1) {
  return Number(v || 0).toFixed(digits);
}

function stateText(v, onText='开启', offText='关闭') {
  return v ? onText : offText;
}

function metricCard(title, value, sub='', cls='') {
  return `<div class="metric"><div class="metric-title">${title}</div><div class="metric-value ${cls}">${value}</div><div class="metric-sub">${sub}</div></div>`;
}

function renderOverview(d) {
  const flow1 = d.flow_rate ? d.flow_rate.flow1 : 0;
  const flow2 = d.flow_rate ? d.flow_rate.flow2 : 0;
  document.getElementById('overview').innerHTML =
    metricCard('当前流程', getStepText(d.sequence.VB100), `关机：${getShutdownText(d.sequence.VB101)}`) +
    metricCard('高压罐压力', `${fmt(d.pressure.high_tank)} kPa`, `目标 ${fmt(d.params.pressure_target)} kPa`) +
    metricCard('阳极压力', `${fmt(d.pressure.anode)} kPa`, '阳极侧压力') +
    metricCard('阴极压力', `${fmt(d.pressure.cathode)} kPa`, '阴极侧压力') +
    metricCard('阳极桶液位', `${fmt(d.level.anode)} cm`, `低于 ${d.level_control.anode_refill_on} 开 / ${d.level_control.refill_off} 停`) +
    metricCard('阴极桶液位', `${fmt(d.level.cathode)} cm`, `低于 ${d.level_control.cathode_refill_on} 开 / ${d.level_control.refill_off} 停`) +
    metricCard('阳极实际流量', `${fmt(flow1, 3)} L/min`, '直流联锁要求 ≥0.500 L/min', d.flags['V2303.3'] ? 'status-ok' : 'status-warn') +
    metricCard('阴极实际流量', `${fmt(flow2, 3)} L/min`, '直流联锁要求 ≥0.050 L/min', d.flags['V2303.4'] ? 'status-ok' : 'status-warn') +
    metricCard('阳极流量系数', `${fmt(d.params.anode_flow_coeff, 0)}`, 'VD2016') +
    metricCard('阴极流量系数', `${fmt(d.params.cathode_flow_coeff, 0)}`, 'VD2028') +
    metricCard('阳极补水阀', stateText(d.outputs['Q0.0']), `Q0.0 ${d.outputs['Q0.0'] ? 'ON' : 'OFF'}`, d.outputs['Q0.0'] ? 'on' : 'off') +
    metricCard('阴极补水阀', stateText(d.outputs['Q0.1']), `Q0.1 ${d.outputs['Q0.1'] ? 'ON' : 'OFF'}`, d.outputs['Q0.1'] ? 'on' : 'off') +
    metricCard('阳极阀', stateText(d.outputs['Q0.2']), `Q0.2 ${d.outputs['Q0.2'] ? 'ON' : 'OFF'}`, d.outputs['Q0.2'] ? 'on' : 'off') +
    metricCard('阴极电磁阀', stateText(d.outputs['Q0.3']), `Q0.3 ${d.outputs['Q0.3'] ? 'ON' : 'OFF'}`, d.outputs['Q0.3'] ? 'on' : 'off') +
    metricCard('制水机', stateText(d.outputs['Q1.0'], '制水中', '停止'), `Q1.0 ${d.outputs['Q1.0'] ? 'ON' : 'OFF'}`, d.outputs['Q1.0'] ? 'on' : 'off') +
    metricCard('空压机', stateText(d.outputs['Q1.1']), `Q1.1 ${d.outputs['Q1.1'] ? 'ON' : 'OFF'}`, d.outputs['Q1.1'] ? 'on' : 'off') +
    metricCard('直流仪输出', stateText(d.outputs['Q1.2'], '允许', '关闭'), `Q1.2 ${d.outputs['Q1.2'] ? 'ON' : 'OFF'}`, d.outputs['Q1.2'] ? 'on' : 'off') +
    metricCard('阳极泵', stateText(d.flags['M1.0'], '运行', '停止'), `AQW32 ${d.pumps.aqw32} / 设定 ${d.pumps.anode_pwm_raw}`, d.flags['M1.0'] ? 'on' : 'off') +
    metricCard('阴极泵', stateText(d.flags['M1.1'], '运行', '停止'), `AQW34 ${d.pumps.aqw34} / 设定 ${d.pumps.cathode_pwm_raw}`, d.flags['M1.1'] ? 'on' : 'off') +
    metricCard('阳极流量计输入', stateText(d.inputs['I0.0'], '有脉冲', '无脉冲'), `HSC0 ${d.flow.HC0} / CTU ${d.flow.CTU0}`, d.inputs['I0.0'] ? 'on' : 'off') +
    metricCard('阴极流量计输入', stateText(d.inputs['I0.6'], '有脉冲', '无脉冲'), `CTU流量 ${d.flow.CTU1_FLOW} / CTU诊断 ${d.flow.CTU1}`, d.inputs['I0.6'] ? 'on' : 'off') +
    metricCard('液位报警', (d.flags['V2303.1'] || d.flags['V2303.2']) ? '报警' : '正常', `阳极 ${d.flags['V2303.1'] ? '报警' : '正常'} / 阴极 ${d.flags['V2303.2'] ? '报警' : '正常'}`, (d.flags['V2303.1'] || d.flags['V2303.2']) ? 'status-bad' : 'status-ok') +
    metricCard('生产缺流报警', d.flags['V2303.5'] ? '报警' : '正常', '生产状态下任一路流量不足会关闭直流', d.flags['V2303.5'] ? 'status-bad' : 'status-ok');
}

function processClass(step, current, shutdown) {
  if (shutdown > 0 && step.kind === 'shutdown') return step.code === shutdown ? 'active' : (step.code < shutdown ? 'done' : '');
  if (shutdown > 0 && step.kind === 'startup') return 'done';
  if (step.kind === 'startup') return step.code === current ? 'active' : (current > step.code ? 'done' : '');
  return '';
}

function renderProcess(d) {
  const steps = [
    {kind:'startup', code:0, title:'待机准备', desc:'所有自动流程停止，补水阀关闭，等待开机命令'},
    {kind:'startup', code:10, title:'补水升压', desc:'空压机运行，任一路需要补水时联动制水机，阳极/阴极液位补到设定停止液位，等待高压罐压力达标'},
    {kind:'startup', code:20, title:'阳极运行', desc:'阳极阀开启，阳极泵运行，现场调节转子流量计到约 18L/min'},
    {kind:'startup', code:30, title:'阴阳极运行', desc:'阴极阀和阴极泵启动，调节阳极约 450mL/min、阴极约 50mL/min，直流仪由现场手动恒流测试'},
    {kind:'shutdown', code:10, title:'关机第一步', desc:'直流停止、制水机停止、阴极阀关闭、阴极泵停止'},
    {kind:'shutdown', code:20, title:'阳极延时关机', desc:'阳极泵和阳极阀继续保持，10分钟后停阳极侧和空压机'}
  ];
  document.getElementById('processList').innerHTML = steps.map((s, i) => {
    const cls = processClass(s, d.sequence.VB100, d.sequence.VB101);
    const state = cls === 'active' ? '当前' : (cls === 'done' ? '完成' : '等待');
    return `<div class="process-step ${cls}"><div class="process-index">${i + 1}</div><div><div class="process-title">${s.title}</div><div class="process-desc">${s.desc}</div></div><div class="process-state">${state}</div></div>`;
  }).join('');
}

function statusItem(name, text, cls) {
  return `<div class="status-item"><div class="status-name">${name}</div><div class="status-text ${cls}">${text}</div></div>`;
}

function renderOperationStatus(d) {
  const anodeLevel = d.level.anode;
  const cathodeLevel = d.level.cathode;
  const pressureReady = d.flags['V2303.0'];
  const anodeAlarm = d.flags['V2303.1'];
  const cathodeAlarm = d.flags['V2303.2'];
  const anodeFlowReady = d.flags['V2303.3'];
  const cathodeFlowReady = d.flags['V2303.4'];
  const flowAlarm = d.flags['V2303.5'];
  const anodeRefill = d.outputs['Q0.0'];
  const cathodeRefill = d.outputs['Q0.1'];
  document.getElementById('operationStatus').innerHTML =
    statusItem('高压罐压力', pressureReady ? '已达标' : '未达标', pressureReady ? 'status-ok' : 'status-warn') +
    statusItem('阳极补水', anodeRefill ? '补水中' : (anodeLevel >= d.level_control.refill_off ? '已到停止液位' : '保持'), anodeRefill ? 'status-warn' : 'status-ok') +
    statusItem('阴极补水', cathodeRefill ? '补水中' : (cathodeLevel >= d.level_control.refill_off ? '已到停止液位' : '保持'), cathodeRefill ? 'status-warn' : 'status-ok') +
    statusItem('阳极低液位', anodeAlarm ? '报警，直流禁止' : '正常', anodeAlarm ? 'status-bad' : 'status-ok') +
    statusItem('阴极低液位', cathodeAlarm ? '报警，直流禁止' : '正常', cathodeAlarm ? 'status-bad' : 'status-ok') +
    statusItem('阳极流量联锁', anodeFlowReady ? '达标' : '未达标', anodeFlowReady ? 'status-ok' : 'status-warn') +
    statusItem('阴极流量联锁', cathodeFlowReady ? '达标' : '未达标', cathodeFlowReady ? 'status-ok' : 'status-warn') +
    statusItem('生产缺流', flowAlarm ? '报警，直流已关闭' : '正常', flowAlarm ? 'status-bad' : 'status-ok') +
    statusItem('直流仪', d.outputs['Q1.2'] ? 'PLC输出允许' : 'PLC输出关闭', d.outputs['Q1.2'] ? 'status-ok' : 'status-warn');
}

let paramsLoaded = false;
let paramDirty = {};

function getStepText(v) {
  const m = {0:'待机', 10:'补水升压', 20:'阳极运行', 30:'阴阳极运行'};
  return m[v] || ('步骤'+v);
}

function getShutdownText(v) {
  const m = {0:'无', 10:'停止直流/阴极', 20:'阳极延时关机'};
  return m[v] || ('步骤'+v);
}

function update() {
  fetch('/api/data').then(r=>r.json()).then(d => {
    if (d.connected) {
      document.getElementById('statusBar').className = 'status-bar online';
      document.getElementById('statusBar').textContent = 'PLC已连接 - 192.168.1.11';
    } else {
      document.getElementById('statusBar').className = 'status-bar offline';
      document.getElementById('statusBar').textContent = 'PLC断开: ' + (d.error||'');
      return;
    }
    renderOverview(d);
    renderProcess(d);
    renderOperationStatus(d);
    renderBool('inputs', d.inputs, inputLabels);
    renderBool('outputs', d.outputs, outputLabels);
    renderValue('analog', d.analog_raw, analogLabels, '');
    renderValue('pressure', d.pressure, pressureLabels, 'kPa');
    renderValue('level', d.level, levelLabels, 'cm');
    if (d.level_control) renderValue('levelControl', d.level_control, levelControlLabels, 'cm');
    renderValue('flow', d.flow, flowLabels, '');
    if (d.hsc_diag) renderValue('hscDiag', d.hsc_diag, hscDiagLabels, '');
    renderValue('flowrate', d.flow_rate, flowRateLabels, 'L/min');
    
    let seqHtml = '';
    for (let [k, v] of Object.entries(d.sequence)) {
      let text = k === 'VB100' ? getStepText(v) : (k === 'VB101' ? getShutdownText(v) : v);
      seqHtml += `<div class="row"><span class="label">${seqLabels[k]||k}</span><span class="value ${v>0?'seq-active':''}">${text}</span></div>`;
    }
    document.getElementById('sequence').innerHTML = seqHtml;
    renderBool('flags', d.flags, flagLabels);
    if (d.pumps) {
      let anodePwm = d.pumps.anode_pwm_raw;
      let cathodePwm = d.pumps.cathode_pwm_raw;
      let aqw32 = d.pumps.aqw32;
      let aqw34 = d.pumps.aqw34;
      let v32 = (aqw32 / 27648 * 10).toFixed(2);
      let v34 = (aqw34 / 27648 * 10).toFixed(2);
      let f32 = (aqw32 / 13824 * 1.0).toFixed(3);
      let f34 = (aqw34 / 13824 * 1.0).toFixed(3);
      document.getElementById('pumps').innerHTML =
        `<div class="row"><span class="label">阳极PWM设定</span><span class="value highlight">${anodePwm}</span></div>` +
        `<div class="row"><span class="label">阴极PWM设定</span><span class="value highlight">${cathodePwm}</span></div>` +
        `<div class="row"><span class="label">阳极泵 AQW32</span><span class="value ${aqw32>0?'on':'off'}">${aqw32} (${v32}V, ${f32}L/min估算)</span></div>` +
        `<div class="row"><span class="label">阴极泵 AQW34</span><span class="value ${aqw34>0?'on':'off'}">${aqw34} (${v34}V, ${f34}L/min估算)</span></div>`;
    }
    if (d.params) {
      if (!paramsLoaded) {
        paramsLoaded = true;
        document.getElementById('levelTarget').value = d.params.level_target;
        document.getElementById('pressureTarget').value = d.params.pressure_target;
        document.getElementById('stepDelay').value = d.params.step_delay;
        document.getElementById('cathodePumpVoltage').value = (d.pumps.cathode_pwm_raw / 27648 * 10).toFixed(2);
      }
      if (!paramDirty['level_target']) document.getElementById('levelTarget').value = d.params.level_target;
      if (!paramDirty['pressure_target']) document.getElementById('pressureTarget').value = d.params.pressure_target;
      if (!paramDirty['step_delay']) document.getElementById('stepDelay').value = d.params.step_delay;
      if (!paramDirty['cathode_pump_voltage']) document.getElementById('cathodePumpVoltage').value = (d.pumps.cathode_pwm_raw / 27648 * 10).toFixed(2);
    }
    document.getElementById('timestamp').textContent = '最后更新: ' + d.timestamp;
  }).catch(e => {
    document.getElementById('statusBar').className = 'status-bar offline';
    document.getElementById('statusBar').textContent = '连接错误';
  });
}

setInterval(update, 500);
update();

function sendControl(action) {
  fetch('/api/control', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: action})
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      document.getElementById('statusBar').textContent = '命令已发送: ' + action;
    } else {
      document.getElementById('statusBar').textContent = '命令失败: ' + (d.error||'');
    }
  });
}

function setParam(name) {
  let inputId = {level_target:'levelTarget', pressure_target:'pressureTarget', step_delay:'stepDelay', cathode_pump_voltage:'cathodePumpVoltage'}[name];
  let value = document.getElementById(inputId).value.trim().replace('，', '.').replace('。', '.');
  fetch('/api/set_param', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: name, value: value})
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      paramDirty[name] = false;
      document.getElementById('statusBar').textContent = '参数已设置: ' + name + '=' + value;
    } else {
      document.getElementById('statusBar').textContent = '设置失败: ' + (d.error||'');
    }
  });
}
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/data')
def api_data():
    return jsonify(plc_data)

if __name__ == '__main__':
    t = threading.Thread(target=read_plc, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=5000, debug=False)
