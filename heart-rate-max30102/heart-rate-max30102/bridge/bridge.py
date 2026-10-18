"""
MAX30102 Serial Bridge
======================
Reads Arduino serial output and serves it to the dashboard via HTTP.

SETUP:
  pip install pyserial flask flask-cors

USAGE:
  1. Close Arduino IDE Serial Monitor (only one program can use COM port at a time)
  2. Edit COM_PORT below to match your Arduino port (check Arduino IDE > Tools > Port)
  3. Run: python bridge.py
  4. Open dashboard.html in your browser
"""

import serial
import re
import threading
import time
from flask import Flask, jsonify
from flask_cors import CORS

# ─── CONFIGURE THIS ────────────────────────────────────────────────
COM_PORT   = "COM13"       # Change to your Arduino port (e.g. COM3, COM5)
BAUD_RATE  = 115200       # Must match Serial.begin() in your Arduino code
# ───────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # Allow dashboard HTML to fetch from this server

# Shared state (updated by serial reader thread)
latest = {
    "ir":      0,
    "bpm":     0.0,
    "avg_bpm": 0,
    "finger":  False,
    "history": []          # last 60 BPM readings for chart
}
lock = threading.Lock()

def read_serial():
    """Background thread: continuously reads from Arduino serial port."""
    pattern = re.compile(
        r"IR=(\d+)\s*\|\s*BPM=([\d.]+)\s*\|\s*Avg BPM=(\d+)"
    )

    print(f"[bridge] Connecting to {COM_PORT} at {BAUD_RATE} baud...")
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=2)
        print(f"[bridge] Connected! Waiting for data...")
    except serial.SerialException as e:
        print(f"[bridge] ERROR: Could not open {COM_PORT} — {e}")
        print("[bridge] Make sure: (1) COM_PORT is correct, (2) Arduino IDE Serial Monitor is CLOSED")
        return

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            match = pattern.search(line)
            if match:
                ir      = int(match.group(1))
                bpm     = float(match.group(2))
                avg_bpm = int(match.group(3))
                finger  = ir >= 50000

                with lock:
                    latest["ir"]      = ir
                    latest["bpm"]     = round(bpm, 1)
                    latest["avg_bpm"] = avg_bpm
                    latest["finger"]  = finger

                    # Keep rolling 60-point history for chart
                    if finger and bpm > 20:
                        latest["history"].append(round(bpm, 1))
                        if len(latest["history"]) > 60:
                            latest["history"].pop(0)

                print(f"IR={ir} | BPM={bpm:.1f} | AvgBPM={avg_bpm} | Finger={'YES' if finger else 'NO'}")

        except Exception as e:
            print(f"[bridge] Read error: {e}")
            time.sleep(1)

@app.route("/data")
def data():
    """Dashboard polls this endpoint every second."""
    with lock:
        return jsonify(latest)

@app.route("/status")
def status():
    return jsonify({"status": "running", "port": COM_PORT})

if __name__ == "__main__":
    # Start serial reader in background thread
    t = threading.Thread(target=read_serial, daemon=True)
    t.start()

    print("[bridge] Dashboard server running at http://localhost:5000")
    print("[bridge] Open dashboard.html in your browser now!")
    print("[bridge] Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
