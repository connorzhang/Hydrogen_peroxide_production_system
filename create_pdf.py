import markdown
import pdfkit
import os
import codecs

html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
    body { font-family: 'Microsoft YaHei', sans-serif; padding: 20px; color: #333; line-height: 1.6; }
    h1 { text-align: center; color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }
    h2 { color: #2563eb; margin-top: 30px; border-left: 4px solid #2563eb; padding-left: 10px; }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px; }
    th, td { border: 1px solid #d1d5db; padding: 10px; text-align: left; }
    th { background-color: #f3f4f6; font-weight: bold; }
    .highlight { background-color: #fef08a; font-weight: bold; }
    .warning { color: #dc2626; font-weight: bold; }
    .box { border: 1px solid #e5e7eb; padding: 15px; background: #f9fafb; border-radius: 5px; margin: 20px 0; }
</style>
</head>
<body>

<h1>双氧水生产系统 - 现场接线确认表</h1>

<div class="box">
    <strong>基本配置要求：</strong><br>
    • PLC型号：S7-200 SMART <b>CPU ST30</b><br>
    • 扩展模块1：<b>AE08</b> (8路模拟量输入)<br>
    • 扩展模块2：<b>AQ02</b> (2路模拟量输出)<br>
    • 程序版本：V16 (对应模块化防干烧版本)
</div>

<h2>1. 物理按钮与传感器输入 (DI / AI)</h2>
<table>
    <tr>
        <th width="15%">端子/地址</th>
        <th width="20%">设备名称</th>
        <th width="30%">接线建议</th>
        <th width="35%">程序作用</th>
    </tr>
    <tr>
        <td class="highlight">I0.1</td>
        <td>开机按钮</td>
        <td>常开触点 (NO)</td>
        <td>触发开机顺控 (点动即可)</td>
    </tr>
    <tr>
        <td class="highlight">I0.2</td>
        <td>关机按钮</td>
        <td>常开触点 (NO)</td>
        <td>触发关机顺控 (点动即可)</td>
    </tr>
    <tr>
        <td class="highlight">I0.3</td>
        <td>急停按钮</td>
        <td><span class="warning">常开触点 (NO)</span></td>
        <td>紧急切断所有Q输出与顺控<br>(注：程序使用常开触发，若接常闭需反相)</td>
    </tr>
    <tr>
        <td class="highlight">I0.0</td>
        <td>阳极流量计脉冲</td>
        <td>接流量计信号线 (需加2K上拉电阻)</td>
        <td>HSC0 高速计数 (脉冲换算)</td>
    </tr>
    <tr>
        <td class="highlight">I0.6</td>
        <td>阴极流量计脉冲</td>
        <td>接流量计信号线 (需加2K上拉电阻)</td>
        <td>HSC1 高速计数 (脉冲换算)</td>
    </tr>
    <tr>
        <td>AIW16 (AE08-CH0)</td>
        <td>高压罐压力变送器</td>
        <td>4-20mA 信号，屏蔽线单端接地</td>
        <td>压力达标与超压报警 (VD2100)</td>
    </tr>
    <tr>
        <td>AIW18 (AE08-CH1)</td>
        <td>阳极液位变送器</td>
        <td>4-20mA 信号，屏蔽线单端接地</td>
        <td>补水控制与防干烧报警 (VD2104)</td>
    </tr>
    <tr>
        <td>AIW20 (AE08-CH2)</td>
        <td>阴极液位变送器</td>
        <td>4-20mA 信号，屏蔽线单端接地</td>
        <td>补水控制与防干烧报警 (VD2108)</td>
    </tr>
</table>

<h2>2. 执行器输出 (DO / AO)</h2>
<table>
    <tr>
        <th width="15%">端子/地址</th>
        <th width="25%">设备名称</th>
        <th width="60%">动作逻辑说明</th>
    </tr>
    <tr>
        <td class="highlight">Q0.0</td>
        <td>阳极补水电磁阀</td>
        <td>开机第一步，阳极液位未满时开启，满80%关闭</td>
    </tr>
    <tr>
        <td class="highlight">Q0.1</td>
        <td>阴极补水电磁阀</td>
        <td>开机第一步，阴极液位未满时开启，满80%关闭</td>
    </tr>
    <tr>
        <td class="highlight">Q0.2</td>
        <td>纯水机 / 制水机</td>
        <td>双桶任一缺水时开启，双桶均满时关闭</td>
    </tr>
    <tr>
        <td class="highlight">Q0.3</td>
        <td>空压机 (控制继电器)</td>
        <td>双桶满水后启动；关机时延时30分钟后关闭</td>
    </tr>
    <tr>
        <td class="highlight">Q0.4</td>
        <td>阳极控制电磁阀</td>
        <td>空压机启动后延时3秒开启</td>
    </tr>
    <tr>
        <td class="highlight">Q0.5</td>
        <td>阴极液体电磁阀</td>
        <td>阴极泵启动后延时3秒开启</td>
    </tr>
    <tr>
        <td class="highlight">Q0.6</td>
        <td>直流电源使能端</td>
        <td>阴极电磁阀开启后，延时5分钟开启</td>
    </tr>
    <tr>
        <td>AQW32 (AQ02-CH0)</td>
        <td>阳极泵调速给定</td>
        <td>0-10V 或 4-20mA (依变频器/驱动器而定)，泵使能时输出</td>
    </tr>
    <tr>
        <td>AQW34 (AQ02-CH1)</td>
        <td>阴极泵调速给定</td>
        <td>0-10V 或 4-20mA (依变频器/驱动器而定)，泵使能时输出</td>
    </tr>
</table>

<div class="box">
    <strong>接线注意事项：</strong>
    <ol>
        <li>电磁阀等感性负载，<span class="warning">严禁直接用 PLC Q 点驱动</span>，必须通过 24V 中间继电器隔离。</li>
        <li>由于霍尔流量计是 NPN 开集电极输出，为防止高速脉冲丢失，强烈建议在 I0.0/I0.6 与 24V+ 之间跨接 <b>2K ~ 4.7K 的上拉电阻</b>。</li>
        <li>模拟量信号极易受变频器干扰，必须使用屏蔽双绞线，并将屏蔽层在机柜接地排处<b>单端可靠接地</b>。</li>
    </ol>
</div>

</body>
</html>
"""

# Save HTML first
with codecs.open('H:\\GIT\\trae\\双氧水生产\\现场接线表_打印版.html', 'w', 'utf-8') as f:
    f.write(html_content)

# Convert to PDF
try:
    options = {
        'page-size': 'A4',
        'margin-top': '15mm',
        'margin-right': '15mm',
        'margin-bottom': '15mm',
        'margin-left': '15mm',
        'encoding': "UTF-8",
        'no-outline': None,
        'enable-local-file-access': None
    }
    pdfkit.from_file('H:\\GIT\\trae\\双氧水生产\\现场接线表_打印版.html', 'H:\\GIT\\trae\\双氧水生产\\现场接线表_打印版.pdf', options=options)
    print("PDF created successfully.")
except Exception as e:
    print(f"Error creating PDF: {e}")
