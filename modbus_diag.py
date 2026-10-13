import snap7
import time
import struct

# PLC IP Address (Please verify if this is correct for your setup)
PLC_IP = '192.168.1.11'  # Please modify if your PLC IP is different

def read_plc_status():
    client = snap7.client.Client()
    try:
        # Connect to S7-200 SMART
        client.connect(PLC_IP, 0, 1)
        print(f"Successfully connected to PLC at {PLC_IP}")

        while True:
            # 1. Read Q1.2 (Power Enable Status)
            # Q memory is area 0x82. We read 1 byte starting at byte 1
            q_data = client.read_area(0x82, 0, 1, 1)
            q1_2 = bool(q_data[0] & (1 << 2))

            # 2. Read M10.2, M10.3, M10.4 (Modbus Control Flags)
            # M memory is area 0x83. We read 1 byte starting at byte 10
            m_data = client.read_area(0x83, 0, 10, 1)
            m10_2 = bool(m_data[0] & (1 << 2)) # MB_CTRL2 Done
            m10_3 = bool(m_data[0] & (1 << 3)) # MB_MSG2 Done
            m10_4 = bool(m_data[0] & (1 << 4)) # MB_MSG2 First Trigger

            # 3. Read VB3102 (MB_CTRL2 Error Code) and VB3106 (MB_MSG2 Error Code)
            # V memory is mapped to DB1 in S7-200 SMART. Read 8 bytes starting at 3100
            v_data = client.read_area(0x84, 1, 3100, 8)
            error_ctrl = v_data[2] # VB3102
            error_msg = v_data[6]  # VB3106
            
            # 4. Read VW3104 (Value being written)
            v_data_word = client.read_area(0x84, 1, 3104, 2)
            write_val = struct.unpack('>H', v_data_word)[0]

            print("\n--- Modbus 485 Diagnostics ---")
            print(f"DC Power Enabled (Q1.2):    {q1_2}")
            print(f"Init Done (M10.2):          {m10_2}  | Init Error (VB3102): {error_ctrl}")
            print(f"Send Triggered (M10.4):     {m10_4}")
            print(f"Send Done (M10.3):          {m10_3}  | Send Error (VB3106): {error_msg}")
            print(f"Value to Write (VW3104):    {write_val}")
            
            if error_ctrl != 0:
                print(f"!! INIT ERROR DETECTED: Code {error_ctrl} (Check Port setup or timeout)")
            if error_msg != 0:
                print(f"!! MSG ERROR DETECTED: Code {error_msg} (e.g., 3=Timeout, 6=Busy, Check wiring A/B or slave address)")

            time.sleep(1.0)

    except Exception as e:
        print(f"Connection or read error: {e}")
    finally:
        client.disconnect()

if __name__ == '__main__':
    print("Starting PLC Modbus Diagnostic Script...")
    read_plc_status()
