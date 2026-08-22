import tkinter as tk
import time
import math
import threading
import random
from collections import deque
from v2v_simulator.sensor_sim import SensorSim
from v2v_simulator.rule_engine import RuleEngine, EVENT_NAMES
from v2v_simulator.ml_engine import MLEngine
from v2v_simulator.v2v_network import V2VNetwork, VehicleStatePacket
from v2v_simulator.serial_bridge import ESP32SerialBridge
from v2v_simulator.risk_engine import RiskEngine

class RealisticV2VSimulator:
    def __init__(self, root, port='/dev/ttyUSB0'):
        self.root = root
        self.root.title("V2V Professional Telemetry Suite")
        self.root.geometry("1000x700")
        self.root.configure(bg="#0F0F13") 
        
        # V2V Core Components
        self.network = V2VNetwork()
        self.bridge = ESP32SerialBridge(self.network, port=port, baudrate=115200)
        self.sensor = SensorSim(initial_speed=0.0)
        self.rule_engine = RuleEngine(speed_limit=25.0) # 90 km/h in m/s
        self.ml_engine = MLEngine()
        self.risk_engine = RiskEngine()
        
        self.vehicle_id = "A"
        self.seq = 0
        
        # Physics State
        self.speed = 0.0
        self.heading = 0.0
        self.accel = 0.0
        self.lat_g = 0.0
        self.lon_g = 0.0
        self.roll = 0.0
        
        # Advanced Physics & Realism
        self.gear = 1
        self.rpm = 800
        self.road_conditions = ["DRY", "WET", "ICE"]
        self.road_idx = 0
        self.eco_score = 100.0
        
        # OBD2 Emulated State
        self.obd_throttle = 0.0
        self.obd_brake = 0.0
        self.obd_steer = 0.0
        self.obd_airbag = False
        
        # Telemetry Graph History
        self.history_speed = deque(maxlen=50)
        self.history_g = deque(maxlen=50)
        
        # Input State
        self.emergency_mode = False
        self.inputs = {
            'up': False, 'down': False, 'left': False, 'right': False, 
            'space': False, 'b': False
        }
        self.throttle_val = 0.0
        self.steer_val = 0.0
        
        self.setup_ui()
        self.bind_keys()
        
        self.running = True
        self.physics_thread = threading.Thread(target=self.physics_loop, daemon=True)
        self.physics_thread.start()
        
        # Start NPC ghost cars
        self.npc_thread = threading.Thread(target=self.npc_loop, daemon=True)
        self.npc_thread.start()
        
    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, bg="#0F0F13", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.font_title = ("Helvetica", 14, "bold")
        self.font_small = ("Helvetica", 12)
        self.font_mono = ("Courier", 12, "bold")
        
        # Dashboard Panel (Left)
        self.canvas.create_rectangle(20, 20, 380, 480, fill="#1F2937", outline="#374151", width=2)
        
        # Arc Speedometer
        self.canvas.create_arc(60, 60, 340, 340, start=150, extent=-120, outline="#374151", width=10, style=tk.ARC)
        self.speed_arc = self.canvas.create_arc(60, 60, 340, 340, start=150, extent=0, outline="#10B981", width=10, style=tk.ARC)
        
        self.speed_text = self.canvas.create_text(200, 200, text="0", fill="#10B981", font=("Helvetica", 64, "bold"))
        self.canvas.create_text(200, 250, text="km/h", fill="#9CA3AF", font=self.font_title)
        
        self.gear_text = self.canvas.create_text(130, 250, text="G: 1", fill="#F59E0B", font=self.font_title)
        self.rpm_text = self.canvas.create_text(270, 250, text="RPM: 800", fill="#F59E0B", font=self.font_title)
        
        # Eco Score
        self.eco_text = self.canvas.create_text(200, 300, text="SAFETY SCORE: 100", fill="#10B981", font=self.font_title)
        
        # Status Box
        self.status_bg = self.canvas.create_rectangle(40, 360, 360, 420, fill="#374151", outline="")
        self.status_text = self.canvas.create_text(200, 390, text="STATUS: NORMAL", fill="#10B981", font=self.font_title)
        self.ml_text = self.canvas.create_text(200, 450, text="ML Anomaly: False", fill="#9CA3AF", font=self.font_small)
        
        # IMU & OBD2 Panel (Right Top)
        self.canvas.create_rectangle(400, 20, 780, 320, fill="#1F2937", outline="#374151", width=2)
        
        self.imu_center_x, self.imu_center_y = 500, 150
        self.imu_radius = 90
        
        self.canvas.create_oval(self.imu_center_x - self.imu_radius, self.imu_center_y - self.imu_radius,
                                self.imu_center_x + self.imu_radius, self.imu_center_y + self.imu_radius,
                                outline="#4B5563", width=2)
                                
        self.bubble = self.canvas.create_oval(self.imu_center_x - 10, self.imu_center_y - 10,
                                              self.imu_center_x + 10, self.imu_center_y + 10,
                                              fill="#10B981", outline="")
                                              
        self.road_text = self.canvas.create_text(680, 60, text="ROAD: DRY", fill="#E5E7EB", font=self.font_title)
        self.ttc_text = self.canvas.create_text(680, 100, text="TTC: SAFE", fill="#10B981", font=self.font_title)
        self.roll_text = self.canvas.create_text(680, 140, text="Roll: 0°", fill="#E5E7EB", font=self.font_title)
        
        # OBD2 LIVE DATA BOX
        self.canvas.create_rectangle(420, 245, 760, 310, fill="#111827", outline="#4B5563")
        self.obd_thr = self.canvas.create_text(500, 265, text="THR: 00%", fill="#9CA3AF", font=self.font_mono)
        self.obd_brk = self.canvas.create_text(500, 290, text="BRK: 00%", fill="#9CA3AF", font=self.font_mono)
        self.obd_str = self.canvas.create_text(680, 265, text="STR:  00°", fill="#9CA3AF", font=self.font_mono)
        self.obd_abg = self.canvas.create_text(680, 290, text="ARBG: OK", fill="#10B981", font=self.font_mono)
        
        # Telemetry Graph (Bottom Right)
        self.canvas.create_rectangle(400, 340, 780, 480, fill="#1F2937", outline="#374151", width=2)
        self.canvas.create_text(450, 360, text="LIVE TELEMETRY", fill="#9CA3AF", font=self.font_small)
        
        self.graph_lines = []
        self.weather_particles = []
        
        # Controls Panel (Bottom)
        self.canvas.create_rectangle(20, 500, 780, 680, fill="#111827", outline="#374151", width=2)
        controls = "CONTROLS:\n[Up/Down]: Drive/Brake    [Left/Right]: Steer\n[B]: Harsh Brake    [Space]: CRASH!\n[W]: Change Weather    [E]: Siren Mode"
        self.canvas.create_text(400, 590, text=controls, fill="#6B7280", font=("Helvetica", 14), justify=tk.CENTER)

    def bind_keys(self):
        self.root.bind("<KeyPress>", self.key_press)
        self.root.bind("<KeyRelease>", self.key_release)
        
    def key_press(self, event):
        keysym = event.keysym.lower()
        if keysym == 'e': 
            self.emergency_mode = not self.emergency_mode
        elif keysym == 'w':
            self.road_idx = (self.road_idx + 1) % 3
        elif keysym in self.inputs: 
            self.inputs[keysym] = True

    def key_release(self, event):
        keysym = event.keysym.lower()
        if keysym in self.inputs: self.inputs[keysym] = False

    def get_friction(self):
        cond = self.road_conditions[self.road_idx]
        if cond == "WET": return 0.4
        elif cond == "ICE": return 0.1
        return 0.8 # DRY

    def npc_loop(self):
        # Simulate ghost cars with dynamic, unpredictable behaviors
        seq_b = 0
        speed_b = 15.0 # m/s (54 km/h)
        while self.running:
            friction = self.get_friction()
            
            # Dynamic NPC braking based on weather
            brake_chance = 0.05 if friction < 0.5 else 0.01
            if random.random() < brake_chance and speed_b > 5.0:
                accel_b = -8.0 # Sudden hard brake
            else:
                accel_b = (15.0 - speed_b) * 0.2 + random.uniform(-0.5, 0.5)
            
            speed_b = max(0.0, speed_b + accel_b * 0.1)
            
            seq_b += 1
            packet_b = VehicleStatePacket(
                vehicle_id="B", seq=seq_b, timestamp=time.time(),
                speed=speed_b, 
                acceleration=accel_b, heading=self.heading, event=0, confidence=100
            )
            self.risk_engine.update_neighbor(packet_b)
            time.sleep(0.1)

    def physics_loop(self):
        dt = 0.05 
        
        while self.running:
            current_time = time.time()
            friction_mod = self.get_friction()
            
            # --- Input Smoothing ---
            if self.inputs['up']: self.throttle_val = min(1.0, self.throttle_val + dt * 2)
            else: self.throttle_val = max(0.0, self.throttle_val - dt * 2)
            
            steer_resp = 3 if friction_mod > 0.3 else 1
            if self.inputs['left']: self.steer_val = max(-1.0, self.steer_val - dt * steer_resp)
            elif self.inputs['right']: self.steer_val = min(1.0, self.steer_val + dt * steer_resp)
            else:
                if self.steer_val > 0: self.steer_val = max(0.0, self.steer_val - dt * 5)
                elif self.steer_val < 0: self.steer_val = min(0.0, self.steer_val + dt * 5)
                
            # Handle roll from physical MPU6050
            if hasattr(self.bridge, 'mpu_accel') and self.bridge.mpu_accel is not None:
                ax, ay, az = self.bridge.mpu_accel
                # Calculate roll angle from accelerometer
                self.roll = math.degrees(math.atan2(ay, az)) if az != 0 else 70.0
            else:
                self.roll = 0.0
                
            # --- Physics Kinematics ---
            speed_kmh = self.speed * 3.6
            self.gear = max(1, min(6, int(speed_kmh / 25) + 1))
            self.rpm = 800 + ((speed_kmh - (self.gear-1)*25) * 120)
            
            engine_force = self.throttle_val * 6.0 
            
            brake_force = 0.0
            if self.inputs['b']: brake_force = 12.0 * friction_mod 
            elif self.inputs['down']: brake_force = 2.0 * friction_mod 
            
            aero_drag = 0.005 * (self.speed ** 2)
            rolling_res = 0.2
            
            self.obd_airbag = False
            if self.inputs['space'] or abs(self.roll) >= 70:
                brake_force = 30.0 
                self.obd_airbag = True
                
            self.accel = engine_force - brake_force - rolling_res - aero_drag
            
            self.speed += self.accel * dt
            effective_accel = self.accel
            
            if self.speed <= 0:
                self.speed = 0
                if not (self.inputs['space'] or self.inputs['b'] or abs(self.roll) >= 70):
                    effective_accel = 0.0
                
            turn_rate = self.steer_val * (self.speed * 0.2)
            self.heading = (self.heading + turn_rate * dt) % 360
            
            self.lon_g = effective_accel / 9.81
            self.lat_g = (turn_rate * self.speed) / 9.81 if self.speed > 0 else 0.0
            
            # Record OBD2 state
            self.obd_throttle = self.throttle_val
            self.obd_brake = min(1.0, brake_force / 12.0) if friction_mod > 0 else 0.0
            if self.obd_airbag: self.obd_brake = 1.0
            self.obd_steer = self.steer_val
            
            # Update Eco / Safety Score
            if abs(self.lon_g) > 0.6 or abs(self.lat_g) > 0.6:
                self.eco_score = max(0.0, self.eco_score - 1.0)
            elif self.obd_airbag:
                self.eco_score = 0.0
            else:
                self.eco_score = min(100.0, self.eco_score + 0.1)
            
            # Graph history
            self.history_speed.append(speed_kmh)
            self.history_g.append(self.lon_g)
            
            # --- V2V Integration (WITH SENSOR NOISE & OBD2 DATA) ---
            noisy_speed = max(0.0, self.speed + random.gauss(0, 0.2))
            noisy_accel = effective_accel + random.gauss(0, 0.1)
            
            # Pass all OBD2 data into the internal vehicle sensor state for ML evaluation
            self.sensor.update(
                noisy_speed, noisy_accel, self.heading,
                throttle=self.obd_throttle,
                brake=self.obd_brake,
                steering=self.obd_steer,
                airbag=self.obd_airbag
            )
            state = self.sensor.get_state()
            
            event_id = self.rule_engine.evaluate(state, current_time)
            
            if self.obd_airbag:
                event_id = 4
                
            if self.emergency_mode:
                event_id = 8
            
            # Calculate Risk Engine first to get TTC Context
            highest_risk, min_ttc, trig_event = self.risk_engine.calculate_risk(state, simulated_distance=30.0)
            
            # ML Engine uses Temporal Sliding Window (10 frames) + TTC/Friction Context
            is_anomaly, ml_score = self.ml_engine.evaluate(state, min_ttc=min_ttc, friction=friction_mod)
            
            # Note: We still send the optimized lightweight packet over V2V radio (ESP32)
            self.seq += 1
            packet = VehicleStatePacket(
                self.vehicle_id, self.seq, current_time,
                noisy_speed, noisy_accel, self.heading,
                event=event_id, confidence=90
            )
            self.bridge.receive_packet(packet.to_json())
            
            self.update_ui(event_id, is_anomaly, ml_score, min_ttc)
            
            time.sleep(dt)

    def draw_graph(self):
        for line in self.graph_lines:
            self.canvas.delete(line)
        self.graph_lines.clear()
        
        if len(self.history_speed) < 2: return
        
        w = 340
        h = 100
        x_start = 420
        y_start = 460
        
        dx = w / len(self.history_speed)
        
        for i in range(1, len(self.history_speed)):
            x1 = x_start + (i-1)*dx
            y1 = y_start - (self.history_speed[i-1] / 160.0) * h
            x2 = x_start + i*dx
            y2 = y_start - (self.history_speed[i] / 160.0) * h
            l = self.canvas.create_line(x1, y1, x2, y2, fill="#10B981", width=2)
            self.graph_lines.append(l)
            
    def draw_weather(self):
        for p in self.weather_particles:
            self.canvas.delete(p)
        self.weather_particles.clear()
        
        cond = self.road_conditions[self.road_idx]
        if cond == "WET":
            for _ in range(20):
                x = random.randint(0, 1000)
                y = random.randint(0, 700)
                l = self.canvas.create_line(x, y, x - 5, y + 15, fill="#3B82F6", width=1)
                self.weather_particles.append(l)
        elif cond == "ICE":
            for _ in range(30):
                x = random.randint(0, 1000)
                y = random.randint(0, 700)
                s = random.randint(2, 4)
                o = self.canvas.create_oval(x, y, x+s, y+s, fill="#FFFFFF", outline="")
                self.weather_particles.append(o)

    def update_ui(self, event_id, is_anomaly, ml_score, ttc):
        speed_kmh = self.speed * 3.6
        
        def _update():
            # Speed Arc
            extent = min(240, (speed_kmh / 160.0) * 240)
            color = "#10B981" if speed_kmh < 90 else "#EF4444"
            self.canvas.itemconfig(self.speed_arc, extent=-extent, outline=color)
            self.canvas.itemconfig(self.speed_text, text=f"{speed_kmh:.0f}", fill=color)
            
            self.canvas.itemconfig(self.gear_text, text=f"G: {self.gear}")
            self.canvas.itemconfig(self.rpm_text, text=f"RPM: {int(self.rpm)}")
            
            score_col = "#10B981" if self.eco_score > 80 else ("#F59E0B" if self.eco_score > 40 else "#EF4444")
            self.canvas.itemconfig(self.eco_text, text=f"SAFETY SCORE: {int(self.eco_score)}", fill=score_col)
            
            # Road & TTC
            cond = self.road_conditions[self.road_idx]
            cond_color = "#3B82F6" if cond == "WET" else "#E5E7EB"
            if cond == "ICE": cond_color = "#93C5FD"
            self.canvas.itemconfig(self.road_text, text=f"ROAD: {cond}", fill=cond_color)
            
            ttc_str = f"TTC: {ttc:.1f}s" if ttc < 100 else "TTC: SAFE"
            ttc_col = "#10B981" if ttc > 3.0 else "#EF4444"
            self.canvas.itemconfig(self.ttc_text, text=ttc_str, fill=ttc_col)
            
            self.canvas.itemconfig(self.roll_text, text=f"Roll: {int(self.roll)}°")
            
            # OBD2 UI Update
            thr_pct = int(self.obd_throttle * 100)
            brk_pct = int(self.obd_brake * 100)
            steer_deg = int(self.obd_steer * 45) # roughly map to degrees
            
            self.canvas.itemconfig(self.obd_thr, text=f"THR: {thr_pct:02d}%", fill="#FCD34D" if thr_pct > 0 else "#9CA3AF")
            self.canvas.itemconfig(self.obd_brk, text=f"BRK: {brk_pct:02d}%", fill="#EF4444" if brk_pct > 0 else "#9CA3AF")
            self.canvas.itemconfig(self.obd_str, text=f"STR: {steer_deg:3d}°", fill="#3B82F6" if abs(steer_deg) > 0 else "#9CA3AF")
            
            if self.obd_airbag:
                self.canvas.itemconfig(self.obd_abg, text="ARBG: DEPLOYED", fill="#EF4444")
            else:
                self.canvas.itemconfig(self.obd_abg, text="ARBG: OK", fill="#10B981")
            
            # G-Force Bubble
            bubble_x = self.imu_center_x + (self.lat_g * self.imu_radius)
            bubble_y = self.imu_center_y - (self.lon_g * self.imu_radius)
            
            g_mag = math.hypot(self.lat_g, self.lon_g)
            b_color = "#10B981" if g_mag < 0.3 else ("#F59E0B" if g_mag < 0.8 else "#EF4444")
            
            dist = math.hypot(bubble_x - self.imu_center_x, bubble_y - self.imu_center_y)
            if dist > self.imu_radius:
                ratio = self.imu_radius / dist
                bubble_x = self.imu_center_x + (bubble_x - self.imu_center_x) * ratio
                bubble_y = self.imu_center_y + (bubble_y - self.imu_center_y) * ratio
                
            self.canvas.coords(self.bubble, bubble_x - 10, bubble_y - 10, bubble_x + 10, bubble_y + 10)
            self.canvas.itemconfig(self.bubble, fill=b_color)
            
            # Status
            status_text = EVENT_NAMES.get(event_id, "UNKNOWN").replace("_", " ")
            if self.obd_airbag: status_text = "CRASH / ROLLOVER!"
                
            if self.emergency_mode:
                flash = int(time.time() * 5) % 2 == 0
                self.canvas.itemconfig(self.status_bg, fill="#1E3A8A" if flash else "#7F1D1D")
                self.canvas.itemconfig(self.status_text, text="EMERGENCY SIREN", fill="#FFF")
            elif event_id > 0:
                self.canvas.itemconfig(self.status_bg, fill="#7F1D1D")
                self.canvas.itemconfig(self.status_text, text=f"STATUS: {status_text}", fill="#FECACA")
            else:
                self.canvas.itemconfig(self.status_bg, fill="#374151")
                self.canvas.itemconfig(self.status_text, text="STATUS: NORMAL", fill="#10B981")
                
            # ML Text
            ml_col = "#EF4444" if is_anomaly else "#9CA3AF"
            self.canvas.itemconfig(self.ml_text, text=f"ML Anomaly: {is_anomaly} (Score: {ml_score:.2f})", fill=ml_col)
                
            self.draw_graph()
            self.draw_weather()

        try:
            self.root.after(0, _update)
        except:
            pass

    def on_closing(self):
        self.running = False
        self.bridge.close()
        self.root.destroy()

if __name__ == "__main__":
    import sys
    port = '/dev/ttyUSB0'
    if len(sys.argv) > 1:
        port = sys.argv[1]
        
    root = tk.Tk()
    app = RealisticV2VSimulator(root, port)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
