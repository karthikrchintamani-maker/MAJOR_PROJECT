#!/usr/bin/env python3
"""
RoadEye Nexus – UDP Telemetry Receiver
  python roadeye_receiver.py          → terminal mode
  python roadeye_receiver.py -k       → terminal mode
  python roadeye_receiver.py -tk      → Tkinter dashboard (graphs + animation)
"""

import socket
import json
import time
import os
import sys
import zlib
import argparse
import threading
from collections import deque
from datetime import datetime

# ---------------- shared config ----------------
HOST = "0.0.0.0"
PORT = 5005
BUFFER_SIZE = 16384
PRINT_EVERY = 0.25
RATE_WINDOW = 2.0
SCREEN_CLEAN_INTERVAL = 10
COUNTDOWN_FROM = 10
HISTORY_LEN = 120          # points kept for graphs

def f(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

# ============================================================
#  TERMINAL MODE
# ============================================================
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def run_terminal():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.settimeout(0.5)

    print(f"[*] RoadEye Nexus terminal receiver on {HOST}:{PORT}")
    print("    Use -tk for graphical dashboard\n")
    time.sleep(0.8)

    packet_times = deque()
    total_packets = 0
    last_seq = None
    dropped = 0
    last_print = 0.0
    last_clean = time.time()
    countdown = COUNTDOWN_FROM
    last_second = int(time.time())

    try:
        while True:
            now = time.time()
            current_second = int(now)
            if current_second != last_second:
                last_second = current_second
                countdown -= 1
                if countdown <= 0:
                    countdown = COUNTDOWN_FROM

            if now - last_clean >= SCREEN_CLEAN_INTERVAL:
                clear_screen()
                last_clean = now
                countdown = COUNTDOWN_FROM

            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
            except socket.timeout:
                if now - last_print > 0.6:
                    print(f"\r[waiting...] scoredown: {countdown:2d}s   ", end="", flush=True)
                    last_print = now
                continue

            total_packets += 1
            packet_times.append(now)
            while packet_times and now - packet_times[0] > RATE_WINDOW:
                packet_times.popleft()

            try:
                payload = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"\n[!] Bad JSON from {addr}")
                continue

            received_crc = payload.pop("crc32", None)
            calc_crc = f"{zlib.crc32(json.dumps(payload, separators=(',', ':')).encode('utf-8')) & 0xFFFFFFFF:08X}"
            crc_match = (received_crc == calc_crc) if received_crc else False
            payload["crc32"] = received_crc
            payload["crc_match"] = crc_match

            seq = payload.get("seq")
            if isinstance(seq, int):
                if last_seq is not None and seq > last_seq + 1:
                    dropped += seq - last_seq - 1
                last_seq = seq

            if now - last_print < PRINT_EVERY:
                continue
            last_print = now

            hz = len(packet_times) / RATE_WINDOW if packet_times else 0.0
            device    = payload.get("device_id", "?")
            ts        = f(payload.get("timestamp"))
            stream_hz = payload.get("stream_hz", "?")
            thermal   = payload.get("thermal_status", "?")
            crc       = f"{received_crc} ({'MATCH' if crc_match else 'FAIL'})"
            sensors   = payload.get("sensors", {})
            health    = payload.get("device_health", {})
            road      = payload.get("road_intelligence", {})
            obd2      = payload.get("obd2", {})
            gps       = sensors.get("gps", {})
            accel     = sensors.get("accel", {})
            gyro      = sensors.get("gyro", {})
            gravity   = sensors.get("gravity", {})
            lin_acc   = sensors.get("linear_accel", {})
            orient    = sensors.get("orientation", {})
            baro      = sensors.get("barometer", {})
            light     = sensors.get("ambient_light", {})
            prox      = sensors.get("proximity", {})
            audio     = sensors.get("audio", {})
            avail     = sensors.get("availability", {})

            print("\033[2J\033[H", end="")
            print("=" * 74)
            print(f"  RoadEye Nexus          {device}")
            print(f"  {addr[0]}:{addr[1]}   pkts:{total_packets}   rate:{hz:5.1f} Hz")
            print(f"  seq:{seq}  dropped:{dropped}  stream_hz:{stream_hz}  thermal:{thermal}")
            print(f"  ts:{ts:.3f} ({datetime.fromtimestamp(ts).strftime('%H:%M:%S.%f')[:-3] if ts else '—'})  crc32:{crc}")
            print(f"  SCREEN CLEAN in: {countdown:2d}s")
            print("=" * 74)

            fix = "FIX" if gps.get("has_fix") else "NO FIX"
            print(f"  GPS      [{fix}]  {f(gps.get('lat')):.6f}, {f(gps.get('lng')):.6f}")
            print(f"           alt={f(gps.get('altitude_m')):6.1f}m  spd={f(gps.get('speed_mps')):5.1f}m/s  "
                  f"brg={f(gps.get('bearing')):5.1f}°  acc={f(gps.get('accuracy_m')):4.1f}m")
            print(f"  Accel    x={f(accel.get('x')):7.3f}  y={f(accel.get('y')):7.3f}  z={f(accel.get('z')):7.3f}")
            print(f"  LinAcc   x={f(lin_acc.get('x')):7.3f}  y={f(lin_acc.get('y')):7.3f}  z={f(lin_acc.get('z')):7.3f}")
            print(f"  Gyro     x={f(gyro.get('x')):7.4f}  y={f(gyro.get('y')):7.4f}  z={f(gyro.get('z')):7.4f}")
            print(f"  Gravity  x={f(gravity.get('x')):7.3f}  y={f(gravity.get('y')):7.3f}  z={f(gravity.get('z')):7.3f}")
            print(f"  Orient   pitch={f(orient.get('pitch_deg')):6.1f}°  roll={f(orient.get('roll_deg')):6.1f}°  yaw={f(orient.get('yaw_deg')):6.1f}°")
            print(f"  Baro     {f(baro.get('pressure_hpa')):7.1f} hPa   rel_alt={f(baro.get('rel_altitude_m')):6.1f} m")
            print(f"  Light    {f(light.get('lux')):7.1f} lux   ({light.get('condition', '?')})")
            print(f"  Prox     {f(prox.get('distance_cm')):5.1f} cm    near={prox.get('is_near', False)}")
            print(f"  Audio    active={audio.get('active', False)}  rms={f(audio.get('rms_dbfs')):5.1f} dBFS  peak={f(audio.get('peak_amp')):.3f}")
            print(f"  Road     score={road.get('condition_score', '?')}  class={road.get('surface_class', '?')}  "
                  f"vib={f(road.get('vibration_rms')):.3f}  impact={road.get('impact_detected', False)}")
            print(f"  Device   bat={health.get('battery_pct', '?')}%  temp={f(health.get('battery_temp_c')):.1f}°C  "
                  f"chg={health.get('charging', False)}  wifi={health.get('wifi_rssi_dbm', '?')}dBm")
            connected = obd2.get("connected", False)
            print(f"  OBD2     [{'CONNECTED' if connected else 'DISCONNECTED'}]  proto={obd2.get('protocol', '?')}")
            if connected:
                print(f"           spd={obd2.get('speed_kmh', 0)}km/h  rpm={obd2.get('rpm', 0)}  "
                      f"thr={f(obd2.get('throttle_pos')):.1f}%  load={f(obd2.get('engine_load')):.1f}%")
                print(f"           cool={obd2.get('coolant_temp_c', 0)}°C  intake={obd2.get('intake_temp_c', 0)}°C  "
                      f"MAF={f(obd2.get('maf_gps')):.2f}g/s  fuel={f(obd2.get('fuel_level_pct')):.1f}%")
            print(f"  Avail    accel={avail.get('accel')} gyro={avail.get('gyro')} baro={avail.get('barometer')} "
                  f"light={avail.get('light')} prox={avail.get('proximity')} audio={avail.get('audio')}")
            print("=" * 74)

    except KeyboardInterrupt:
        print("\n\n[*] Stopped.")
    finally:
        sock.close()

# ============================================================
#  TKINTER DASHBOARD MODE
# ============================================================
def run_tkinter():
    try:
        import tkinter as tk
        from tkinter import ttk
        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        from matplotlib.animation import FuncAnimation
    except ImportError as e:
        print("Tkinter / matplotlib required for -tk mode.")
        print("Install with:  pip install matplotlib")
        print("Error:", e)
        sys.exit(1)

    state = {
        "payload": None,
        "hz": 0.0,
        "total": 0,
        "dropped": 0,
        "addr": "",
        "lock": threading.Lock(),
    }
    history = {
        "t": deque(maxlen=HISTORY_LEN),
        "speed": deque(maxlen=HISTORY_LEN),
        "rpm": deque(maxlen=HISTORY_LEN),
        "accel_z": deque(maxlen=HISTORY_LEN),
        "lin_x": deque(maxlen=HISTORY_LEN),
        "vib": deque(maxlen=HISTORY_LEN),
        "baro": deque(maxlen=HISTORY_LEN),
    }

    def network_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.settimeout(1.0)
        packet_times = deque()
        last_seq = None
        dropped = 0
        total = 0
        while running[0]:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break
            total += 1
            now = time.time()
            packet_times.append(now)
            while packet_times and now - packet_times[0] > RATE_WINDOW:
                packet_times.popleft()
            try:
                payload = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue

            received_crc = payload.pop("crc32", None)
            calc_crc = f"{zlib.crc32(json.dumps(payload, separators=(',', ':')).encode('utf-8')) & 0xFFFFFFFF:08X}"
            crc_match = (received_crc == calc_crc) if received_crc else False
            payload["crc32"] = received_crc
            payload["crc_match"] = crc_match

            seq = payload.get("seq")
            if isinstance(seq, int):
                if last_seq is not None and seq > last_seq + 1:
                    dropped += seq - last_seq - 1
                last_seq = seq
            hz = len(packet_times) / RATE_WINDOW if packet_times else 0.0

            sensors = payload.get("sensors", {})
            obd2 = payload.get("obd2", {})
            road = payload.get("road_intelligence", {})
            gps = sensors.get("gps", {})
            accel = sensors.get("accel", {})
            lin = sensors.get("linear_accel", {})
            baro = sensors.get("barometer", {})

            with state["lock"]:
                state["payload"] = payload
                state["hz"] = hz
                state["total"] = total
                state["dropped"] = dropped
                state["addr"] = f"{addr[0]}:{addr[1]}"
                history["t"].append(now)
                history["speed"].append(f(obd2.get("speed_kmh") or gps.get("speed_mps", 0) * 3.6))
                history["rpm"].append(f(obd2.get("rpm")))
                history["accel_z"].append(f(accel.get("z")))
                history["lin_x"].append(f(lin.get("x")))
                history["vib"].append(f(road.get("vibration_rms")))
                history["baro"].append(f(baro.get("pressure_hpa")))
        sock.close()

    running = [True]
    net_thread = threading.Thread(target=network_loop, daemon=True)
    net_thread.start()

    root = tk.Tk()
    root.title("RoadEye Nexus – Live Dashboard")
    root.geometry("1180x780")
    root.configure(bg="#0d1117")

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TLabel", background="#0d1117", foreground="#e6edf3", font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground="#58a6ff")
    style.configure("Value.TLabel", font=("Consolas", 11), foreground="#3fb950")
    style.configure("Warn.TLabel", font=("Consolas", 11), foreground="#d29922")

    top = tk.Frame(root, bg="#161b22", height=48)
    top.pack(fill="x", padx=6, pady=4)
    lbl_title = ttk.Label(top, text="RoadEye Nexus", style="Title.TLabel")
    lbl_title.pack(side="left", padx=10)
    lbl_status = ttk.Label(top, text="Waiting for packets…", style="TLabel")
    lbl_status.pack(side="left", padx=20)
    lbl_rate = ttk.Label(top, text="0.0 Hz", style="Value.TLabel")
    lbl_rate.pack(side="right", padx=12)

    main_f = tk.Frame(root, bg="#0d1117")
    main_f.pack(fill="both", expand=True, padx=6, pady=4)

    left = tk.Frame(main_f, bg="#0d1117", width=340)
    left.pack(side="left", fill="y", padx=(0, 6))

    def make_card(parent, title):
        fr = tk.Frame(parent, bg="#161b22", bd=1, relief="solid")
        fr.pack(fill="x", pady=4)
        ttk.Label(fr, text=title, style="Title.TLabel").pack(anchor="w", padx=8, pady=(6, 2))
        body = tk.Frame(fr, bg="#161b22")
        body.pack(fill="x", padx=8, pady=(0, 8))
        return body

    def add_row(parent, label):
        row = tk.Frame(parent, bg="#161b22")
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=label, width=14).pack(side="left")
        val = ttk.Label(row, text="—", style="Value.TLabel")
        val.pack(side="left")
        return val

    gps_card = make_card(left, "GPS")
    v_lat = add_row(gps_card, "Latitude")
    v_lng = add_row(gps_card, "Longitude")
    v_alt = add_row(gps_card, "Altitude")
    v_spd = add_row(gps_card, "Speed")
    v_fix = add_row(gps_card, "Fix")

    imu_card = make_card(left, "IMU / Orientation")
    v_ax = add_row(imu_card, "Accel X/Y/Z")
    v_lx = add_row(imu_card, "LinAcc X")
    v_pitch = add_row(imu_card, "Pitch / Roll")
    v_yaw = add_row(imu_card, "Yaw")

    env_card = make_card(left, "Environment")
    v_baro = add_row(env_card, "Pressure")
    v_light = add_row(env_card, "Light")
    v_prox = add_row(env_card, "Proximity")
    v_audio = add_row(env_card, "Audio RMS")

    road_card = make_card(left, "Road / Device")
    v_road = add_row(road_card, "Condition")
    v_vib = add_row(road_card, "Vibration")
    v_bat = add_row(road_card, "Battery")
    v_thermal = add_row(road_card, "Thermal")

    obd_card = make_card(left, "OBD-II")
    v_obd_spd = add_row(obd_card, "Speed / RPM")
    v_thr = add_row(obd_card, "Throttle / Load")
    v_temp = add_row(obd_card, "Coolant / Intake")
    v_fuel = add_row(obd_card, "Fuel / MAF")

    right = tk.Frame(main_f, bg="#0d1117")
    right.pack(side="right", fill="both", expand=True)

    fig = Figure(figsize=(8, 7), dpi=100, facecolor="#0d1117")
    axes = fig.subplots(3, 2)
    fig.tight_layout(pad=2.0)

    titles = [
        ("Speed (km/h)", "speed", "#58a6ff"),
        ("RPM", "rpm", "#f778ba"),
        ("Accel Z", "accel_z", "#3fb950"),
        ("Lin Accel X", "lin_x", "#d29922"),
        ("Vibration RMS", "vib", "#ff7b72"),
        ("Barometer (hPa)", "baro", "#a371f7"),
    ]
    lines = []
    for ax, (title, key, color) in zip(axes.flat, titles):
        ax.set_facecolor("#161b22")
        ax.set_title(title, color="#e6edf3", fontsize=9)
        ax.tick_params(colors="#8b949e", labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        line, = ax.plot([], [], color=color, lw=1.4)
        lines.append((line, key, ax))

    canvas = FigureCanvasTkAgg(fig, master=right)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    def update_ui():
        with state["lock"]:
            payload = state["payload"]
            hz = state["hz"]
            total = state["total"]
            dropped = state["dropped"]
            addr = state["addr"]
            t = list(history["t"])
            hist = {k: list(history[k]) for k in history if k != "t"}

        lbl_rate.config(text=f"{hz:.1f} Hz")
        if payload is None:
            lbl_status.config(text="Waiting for packets…")
            root.after(200, update_ui)
            return

        device = payload.get("device_id", "?")
        seq = payload.get("seq", "?")
        thermal = payload.get("thermal_status", "?")
        lbl_status.config(text=f"{device}  |  {addr}  |  seq={seq}  dropped={dropped}  thermal={thermal}")

        sensors = payload.get("sensors", {})
        health  = payload.get("device_health", {})
        road    = payload.get("road_intelligence", {})
        obd2    = payload.get("obd2", {})
        gps     = sensors.get("gps", {})
        accel   = sensors.get("accel", {})
        lin     = sensors.get("linear_accel", {})
        orient  = sensors.get("orientation", {})
        baro    = sensors.get("barometer", {})
        light   = sensors.get("ambient_light", {})
        prox    = sensors.get("proximity", {})
        audio   = sensors.get("audio", {})

        v_lat.config(text=f"{f(gps.get('lat')):.6f}")
        v_lng.config(text=f"{f(gps.get('lng')):.6f}")
        v_alt.config(text=f"{f(gps.get('altitude_m')):.1f} m")
        v_spd.config(text=f"{f(gps.get('speed_mps')):.1f} m/s")
        v_fix.config(text="FIX" if gps.get("has_fix") else "NO FIX")

        v_ax.config(text=f"{f(accel.get('x')):.2f} / {f(accel.get('y')):.2f} / {f(accel.get('z')):.2f}")
        v_lx.config(text=f"{f(lin.get('x')):.3f}")
        v_pitch.config(text=f"{f(orient.get('pitch_deg')):.1f}° / {f(orient.get('roll_deg')):.1f}°")
        v_yaw.config(text=f"{f(orient.get('yaw_deg')):.1f}°")

        v_baro.config(text=f"{f(baro.get('pressure_hpa')):.1f} hPa")
        v_light.config(text=f"{f(light.get('lux')):.0f} lux ({light.get('condition', '?')})")
        v_prox.config(text=f"{f(prox.get('distance_cm')):.1f} cm  near={prox.get('is_near')}")
        v_audio.config(text=f"{f(audio.get('rms_dbfs')):.1f} dBFS")

        v_road.config(text=f"{road.get('condition_score', '?')} / {road.get('surface_class', '?')}")
        v_vib.config(text=f"{f(road.get('vibration_rms')):.3f}")
        v_bat.config(text=f"{health.get('battery_pct', '?')}%  {f(health.get('battery_temp_c')):.1f}°C")
        v_thermal.config(text=str(thermal))

        connected = obd2.get("connected", False)
        if connected:
            v_obd_spd.config(text=f"{obd2.get('speed_kmh', 0)} km/h   {obd2.get('rpm', 0)} rpm")
            v_thr.config(text=f"{f(obd2.get('throttle_pos')):.1f}%   {f(obd2.get('engine_load')):.1f}%")
            v_temp.config(text=f"{obd2.get('coolant_temp_c', 0)}°C   {obd2.get('intake_temp_c', 0)}°C")
            v_fuel.config(text=f"{f(obd2.get('fuel_level_pct')):.1f}%   MAF {f(obd2.get('maf_gps')):.2f}")
        else:
            v_obd_spd.config(text="—")
            v_thr.config(text="—")
            v_temp.config(text="—")
            v_fuel.config(text="DISCONNECTED")

        if t:
            t0 = t[0]
            xs = [x - t0 for x in t]
            for line, key, ax in lines:
                ys = hist.get(key, [])
                if len(xs) == len(ys) and ys:
                    line.set_data(xs, ys)
                    ax.relim()
                    ax.autoscale_view()
            canvas.draw_idle()

        root.after(150, update_ui)

    def on_close():
        running[0] = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(200, update_ui)
    root.mainloop()

# ============================================================
#  ENTRY
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="RoadEye Nexus UDP Receiver")
    parser.add_argument("-tk", action="store_true", help="Launch Tkinter dashboard")
    parser.add_argument("-k", action="store_true", help="Terminal mode (default)")
    args = parser.parse_args()

    if args.tk:
        run_tkinter()
    else:
        run_terminal()

if __name__ == "__main__":
    main()
