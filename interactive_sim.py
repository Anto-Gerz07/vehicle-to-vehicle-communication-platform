import tkinter as tk
import time
import math
import threading
import random
import csv
import datetime
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
        self.root.geometry("1350x850")
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
        self.speed = 0.0 # m/s
        self.heading = 0.0
        self.accel = 0.0
        self.lat_g = 0.0
        self.lon_g = 0.0
        self.roll = 0.0
        self.pitch = 0.0
        self.rollover_limit = 65.0
        self.last_az = 9.80665 # For pothole jerk calculation
        
        # Advanced Physics & Realism
        self.gear = 1
        self.rpm = 800
        self.eco_score = 100.0
        
        # Vehicle Specs
        self.mass = 1500.0 # kg
        self.wheel_radius = 0.33 # m
        self.track_width = 1.6 # m
        self.final_drive = 3.8
        self.gear_ratios = {1: 3.5, 2: 2.0, 3: 1.4, 4: 1.0, 5: 0.8, 6: 0.6}
        self.air_density = 1.225
        self.drag_coeff = 0.3
        self.frontal_area = 2.2
        self.rolling_res = 0.015
        
        # OBD2 Emulated State (Mode 01 PIDs)
        self.obd_throttle = 0.0
        self.obd_brake = 0.0
        self.obd_steer = 0.0
        self.obd_airbag = False
        
        self.obd_engine_load = 0.0
        self.obd_coolant_temp = 20.0
        self.obd_intake_air_temp = 25.0
        self.obd_maf = 0.0
        self.obd_fuel_level = 100.0
        self.obd_intake_man_pressure = 100.0
        
        # V2V Chassis State
        self.sas_angle = 0.0
        self.abs_fl = 0.0
        self.abs_fr = 0.0
        self.abs_rl = 0.0
        self.abs_rr = 0.0
        self.tcs_active = False
        
        # Telemetry Graph History
        self.history_speed = deque(maxlen=60)
        self.history_g = deque(maxlen=60)
        
        # Input State
        self.emergency_mode = False
        # Keyboard State
        self.inputs = {'up': False, 'w': False, 'down': False, 'left': False, 'right': False, 'b': False, 'space': False}
        self.throttle_val = 0.0
        self.steer_val = 0.0
        
        # Initialize Black Box Logger
        self.log_filename = f"v2v_blackbox_{int(time.time())}.csv"
        self.last_log_time = 0
        with open(self.log_filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Lat', 'Lon', 'Speed_kmh', 'Heading', 'Accel_Z', 'Roll', 'Pitch', 'Event_ID', 'Eco_Score'])
        
        self.setup_ui()
        self.bind_keys()
        
        self.running = True
        self.physics_thread = threading.Thread(target=self.physics_loop, daemon=True)
        self.physics_thread.start()
        
        # Start NPC ghost cars
        self.npc_thread = threading.Thread(target=self.npc_loop, daemon=True)
        self.npc_thread.start()

    def get_torque(self, rpm):
        # Simulated torque curve: peak torque 600Nm at 4000 RPM (Sports Car for easy TCS testing)
        if rpm < 800: return 0
        if rpm > 7000: return 0
        return 600 - ( (rpm - 4000) / 1000 )**2 * 10
        
    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, bg="#0F0F13", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.font_title = ("Helvetica", 18, "bold")
        self.font_small = ("Helvetica", 14)
        self.font_mono = ("Courier", 14, "bold")
        
        # Dashboard Panel (Left)
        self.canvas.create_rectangle(30, 30, 530, 600, fill="#1F2937", outline="#374151", width=2)
        
        # Arc Speedometer
        self.canvas.create_arc(80, 80, 480, 480, start=150, extent=-120, outline="#374151", width=15, style=tk.ARC)
        self.speed_arc = self.canvas.create_arc(80, 80, 480, 480, start=150, extent=0, outline="#10B981", width=15, style=tk.ARC)
        
        self.speed_text = self.canvas.create_text(280, 260, text="0", fill="#10B981", font=("Helvetica", 84, "bold"))
        self.canvas.create_text(280, 340, text="km/h", fill="#9CA3AF", font=self.font_title)
        
        self.gear_text = self.canvas.create_text(160, 340, text="G: 1", fill="#F59E0B", font=self.font_title)
        self.rpm_text = self.canvas.create_text(400, 340, text="RPM: 800", fill="#F59E0B", font=self.font_title)
        
        # Eco Score
        self.eco_text = self.canvas.create_text(280, 420, text="SAFETY SCORE: 100", fill="#10B981", font=self.font_title)
        
        # Status Box
        self.status_bg = self.canvas.create_rectangle(60, 480, 500, 540, fill="#374151", outline="")
        self.status_text = self.canvas.create_text(280, 510, text="STATUS: NORMAL", fill="#10B981", font=self.font_title)
        self.ml_text = self.canvas.create_text(280, 570, text="ML Anomaly: False", fill="#9CA3AF", font=self.font_small)
        
        # IMU & OBD2 Panel (Right Top)
        self.canvas.create_rectangle(560, 30, 1320, 400, fill="#1F2937", outline="#374151", width=2)
        
        self.imu_center_x, self.imu_center_y = 700, 160
        self.imu_radius = 100
        
        self.canvas.create_oval(self.imu_center_x - self.imu_radius, self.imu_center_y - self.imu_radius,
                                self.imu_center_x + self.imu_radius, self.imu_center_y + self.imu_radius,
                                outline="#4B5563", width=2)
                                
        self.bubble = self.canvas.create_oval(self.imu_center_x - 12, self.imu_center_y - 12,
                                              self.imu_center_x + 12, self.imu_center_y + 12,
                                              fill="#10B981", outline="")
        
        # IMU Raw Data
        self.canvas.create_text(910, 100, text="ACCELEROMETER (m/s²)", fill="#6B7280", font=("Helvetica", 11, "bold"))
        self.accel_ui = self.canvas.create_text(910, 130, text="X:0.0 Y:0.0 Z:0.0", fill="#10B981", font=self.font_mono)
        self.canvas.create_text(910, 170, text="GYROSCOPE (rad/s)", fill="#6B7280", font=("Helvetica", 11, "bold"))
        self.gyro_ui = self.canvas.create_text(910, 200, text="X:0.0 Y:0.0 Z:0.0", fill="#F59E0B", font=self.font_mono)
                                              
        # V2V Chassis & Safety Info
        self.tcs_text = self.canvas.create_text(1160, 60, text="TCS/ABS: INACTIVE", fill="#10B981", font=self.font_title)
        self.ttc_text = self.canvas.create_text(1160, 110, text="TTC: SAFE", fill="#10B981", font=self.font_title)
        self.roll_text = self.canvas.create_text(1160, 160, text="Roll: 0°", fill="#E5E7EB", font=self.font_title)
        self.sas_text = self.canvas.create_text(1160, 210, text="SAS: 0°", fill="#3B82F6", font=self.font_title)
        
        # OBD2 LIVE DATA BOX (Restored Driver Inputs & Extended PIDs)
        self.canvas.create_rectangle(580, 250, 840, 370, fill="#111827", outline="#4B5563")
        self.canvas.create_text(710, 270, text="OBD2 LIVE DATA", fill="#6B7280", font=("Helvetica", 11, "bold"))
        
        # Column 1 (Driver)
        self.obd_thr = self.canvas.create_text(640, 295, text="THR: 00%", fill="#9CA3AF", font=self.font_mono)
        self.obd_brk = self.canvas.create_text(640, 320, text="BRK: 00%", fill="#9CA3AF", font=self.font_mono)
        self.obd_abg = self.canvas.create_text(640, 345, text="ARBG: OK", fill="#10B981", font=self.font_mono)
        
        # Column 2 (Engine)
        self.obd_load_ui = self.canvas.create_text(780, 295, text="LOD: 00%", fill="#9CA3AF", font=self.font_mono)
        self.obd_cool_ui = self.canvas.create_text(780, 320, text="ECT: 00°C", fill="#9CA3AF", font=self.font_mono)
        self.obd_maf_ui = self.canvas.create_text(780, 345, text="MAF: 00g/s", fill="#9CA3AF", font=self.font_mono)
        
        # ABS 4-Wheel Speeds Box
        self.canvas.create_rectangle(860, 250, 1300, 370, fill="#111827", outline="#4B5563")
        self.canvas.create_text(1080, 270, text="ABS WHEEL SPEEDS (km/h)", fill="#6B7280", font=("Helvetica", 11, "bold"))
        self.abs_fl_ui = self.canvas.create_text(950, 310, text="FL: 0.0", fill="#9CA3AF", font=self.font_mono)
        self.abs_fr_ui = self.canvas.create_text(1210, 310, text="FR: 0.0", fill="#9CA3AF", font=self.font_mono)
        self.abs_rl_ui = self.canvas.create_text(950, 340, text="RL: 0.0", fill="#9CA3AF", font=self.font_mono)
        self.abs_rr_ui = self.canvas.create_text(1210, 340, text="RR: 0.0", fill="#9CA3AF", font=self.font_mono)
        
        # GPS NEO-6M
        self.gps_ui = self.canvas.create_text(940, 385, text="GPS: AWAITING SATELLITE LOCK", fill="#3B82F6", font=("Courier", 12, "bold"))
        self.gps_extra_ui = self.canvas.create_text(940, 405, text="SPD: -- km/h  HDG: --°  SATS: --", fill="#6B7280", font=("Courier", 11, "bold"))
        
        # Telemetry Graph (Bottom Right)
        self.canvas.create_rectangle(560, 420, 1320, 600, fill="#1F2937", outline="#374151", width=2)
        self.canvas.create_text(630, 440, text="LIVE TELEMETRY", fill="#9CA3AF", font=self.font_small)
        
        self.graph_lines = []
        
        # Controls Panel (Bottom)
        self.canvas.create_rectangle(30, 630, 1320, 820, fill="#111827", outline="#374151", width=2)
        controls = "CONTROLS:\n[W] / [Up]: Normal / Harsh Drive    [Down]: Brake    [Left/Right]: Steer\n[B]: Harsh Brake    [Space]: CRASH!    [E]: Siren Mode"
        self.canvas.create_text(675, 725, text=controls, fill="#6B7280", font=("Helvetica", 16), justify=tk.CENTER)

    def bind_keys(self):
        self.root.bind("<KeyPress>", self.key_press)
        self.root.bind("<KeyRelease>", self.key_release)
        
    def key_press(self, event):
        keysym = event.keysym.lower()
        if keysym == 'e': 
            self.emergency_mode = not self.emergency_mode
        elif keysym in self.inputs: 
            self.inputs[keysym] = True

    def key_release(self, event):
        keysym = event.keysym.lower()
        if keysym in self.inputs: self.inputs[keysym] = False

    def npc_loop(self):
        # Simulate ghost cars with dynamic, unpredictable behaviors
        seq_b = 0
        speed_b = 15.0 # m/s (54 km/h)
        
        # We will spawn the ghost car exactly 100m South of the physical GPS
        lat_b = 0.0
        lon_b = 0.0
        r_earth = 6378137.0
        spawned = False
        
        while self.running:
            local_lat = getattr(self.bridge, 'gps_lat', None)
            local_lon = getattr(self.bridge, 'gps_lon', None)
            
            if local_lat and local_lon and not spawned:
                # Spawn 100m South
                lat_b = local_lat + (-100.0 / r_earth) * (180.0 / math.pi)
                lon_b = local_lon
                spawned = True
                print(f"[Ghost Car] Spawned 100m South of {local_lat}, {local_lon}")
                
            if spawned:
                # Ghost car drives North (Heading 0) at speed_b
                dy = speed_b * 0.1 # m per 0.1s tick
                lat_b = lat_b + (dy / r_earth) * (180.0 / math.pi)
            else:
                lat_b, lon_b = 0.0, 0.0
            
            # Dynamic NPC braking based on random hazard
            if random.random() < 0.02 and speed_b > 5.0:
                accel_b = -8.0 # Sudden hard brake
            else:
                accel_b = (15.0 - speed_b) * 0.2 + random.uniform(-0.5, 0.5)
            
            speed_b = max(0.0, speed_b + accel_b * 0.1)
            
            seq_b += 1
            packet_b = VehicleStatePacket(
                vehicle_id="B", seq=seq_b, timestamp=time.time(),
                speed=speed_b, 
                acceleration=accel_b, heading=0.0, event=0, confidence=100,
                latitude=lat_b, longitude=lon_b
            )
            self.risk_engine.update_neighbor(packet_b)
            time.sleep(0.1)

    def physics_loop(self):
        dt = 0.05 
        friction_mod = 1.0 # Static Dry Asphalt
        
        while self.running:
            current_time = time.time()
            
            # --- Input Smoothing ---
            # W = Normal Drive (max 45% throttle, smooth), Up = Harsh Drive (100% throttle, fast)
            if self.inputs['up']: 
                self.throttle_val = min(1.0, self.throttle_val + dt * 2.5) # Very fast response
            elif self.inputs['w']:
                self.throttle_val = min(0.45, self.throttle_val + dt * 0.5) # Gentle, smooth response
            else: 
                self.throttle_val = max(0.0, self.throttle_val - dt * 1.5)
            
            # Gradual Steering (takes 1.2s to reach full lock, returns to center naturally)
            steer_resp = 0.8
            if self.inputs['left']: self.steer_val = max(-1.0, self.steer_val - dt * steer_resp)
            elif self.inputs['right']: self.steer_val = min(1.0, self.steer_val + dt * steer_resp)
            else:
                if self.steer_val > 0: self.steer_val = max(0.0, self.steer_val - dt * 1.5)
                elif self.steer_val < 0: self.steer_val = min(0.0, self.steer_val + dt * 1.5)
                
            self.sas_angle = self.steer_val * 450.0 # Steering Angle Sensor (-450 to +450)
                
            # Handle roll and pitch from physical MPU6500
            pothole_detected = False
            if hasattr(self.bridge, 'mpu_accel') and self.bridge.mpu_accel is not None:
                ax, ay, az = self.bridge.mpu_accel
                self.roll = math.degrees(math.atan2(ay, math.sqrt(ax*ax + az*az)))
                self.pitch = math.degrees(math.atan2(-ax, math.sqrt(ay*ay + az*az)))
                # Z-Axis Pothole Detection using Jerk (Derivative of Acceleration)
                # A pothole is a SHOCK, meaning acceleration changes instantly. 
                jerk_z = (az - self.last_az) / dt
                self.last_az = az
                
                # If the jerk exceeds 100 m/s³ (a very sharp, sudden jolt), it's a pothole
                if abs(jerk_z) > 100.0:
                    pothole_detected = True
            else:
                self.roll = 0.0
                self.pitch = 0.0
                
            # --- Accurate Physics Kinematics ---
            
            wheel_rpm = (self.speed * 60) / (2 * math.pi * self.wheel_radius)
            self.rpm = max(800.0, wheel_rpm * self.final_drive * self.gear_ratios[self.gear])
            
            if self.rpm > 6000 and self.gear < 6:
                self.gear += 1
            elif self.rpm < 2000 and self.gear > 1:
                self.gear -= 1
                
            self.rpm = max(800.0, wheel_rpm * self.final_drive * self.gear_ratios[self.gear])
            
            engine_torque = self.get_torque(self.rpm) * self.throttle_val
            wheel_torque = engine_torque * self.gear_ratios[self.gear] * self.final_drive
            engine_force = wheel_torque / self.wheel_radius
            
            aero_drag = 0.5 * self.air_density * self.drag_coeff * self.frontal_area * (self.speed ** 2)
            rolling_drag = self.rolling_res * self.mass * 9.81
            
            brake_input = 0.0
            if self.inputs['b']: brake_input = 1.0 
            elif self.inputs['down']: brake_input = 0.12 
            
            requested_brake_force = brake_input * 25000.0 
            
            # Traction Circle Physics (Lateral vs Longitudinal Grip)
            max_friction_force = friction_mod * self.mass * 9.81
            
            turn_rate = self.steer_val * (self.speed * 0.2)
            lat_force = self.mass * (turn_rate * self.speed) # Centripetal Force F = m*v^2/r
            
            # Available longitudinal grip reduces as lateral force increases
            available_lon_force = 0.0
            if max_friction_force**2 > lat_force**2:
                available_lon_force = math.sqrt(max_friction_force**2 - lat_force**2)
            
            # TCS / ABS Activation Logic
            self.tcs_active = False
            
            # If turning so hard we exceed max friction even without pedals
            if abs(lat_force) > max_friction_force:
                self.tcs_active = True
                
            if requested_brake_force > available_lon_force:
                self.tcs_active = True
                brake_force = available_lon_force
            else:
                brake_force = requested_brake_force
                
            if engine_force > available_lon_force:
                self.tcs_active = True
                engine_force = available_lon_force
            
            # Calculate dynamic rollover threshold based on speed (km/h)
            speed_kmh_current = self.speed * 3.6
            # 0 km/h -> 65°, 100 km/h -> 40°, 200 km/h -> 15°
            self.rollover_limit = max(15.0, 65.0 - (speed_kmh_current * 0.25))
            
            self.obd_airbag = False
            if self.inputs['space'] or abs(self.roll) >= self.rollover_limit or abs(self.pitch) >= self.rollover_limit:
                brake_force = max_friction_force 
                self.obd_airbag = True
                self.tcs_active = True
                
            # 5. Net Force and Acceleration
            net_force = engine_force - aero_drag - rolling_drag - brake_force
            
            # If speed is 0 and no throttle, vehicle doesn't move backward
            if self.speed <= 0 and net_force < 0:
                net_force = 0
                
            self.accel = net_force / self.mass
            
            self.speed += self.accel * dt
            effective_accel = self.accel
            
            if self.speed <= 0:
                self.speed = 0
                if not (self.inputs['space'] or self.inputs['b'] or abs(self.roll) >= self.rollover_limit or abs(self.pitch) >= self.rollover_limit):
                    effective_accel = 0.0
                
            turn_rate = self.steer_val * (self.speed * 0.2)
            self.heading = (self.heading + turn_rate * dt) % 360
            
            self.lon_g = effective_accel / 9.81
            self.lat_g = (turn_rate * self.speed) / 9.81 if self.speed > 0 else 0.0
            
            # ABS 4-Wheel Speed Calculation (Differential speed when turning)
            speed_kmh = self.speed * 3.6
            turn_radius = (self.speed / (turn_rate + 0.0001)) if turn_rate != 0 else float('inf')
            
            if turn_rate != 0:
                inner_radius = abs(turn_radius) - (self.track_width / 2)
                outer_radius = abs(turn_radius) + (self.track_width / 2)
                ratio_inner = inner_radius / abs(turn_radius)
                ratio_outer = outer_radius / abs(turn_radius)
                
                if turn_rate > 0: # Turning Right
                    self.abs_fl = speed_kmh * ratio_outer
                    self.abs_fr = speed_kmh * ratio_inner
                    self.abs_rl = speed_kmh * ratio_outer * 0.98 # slight rear slip
                    self.abs_rr = speed_kmh * ratio_inner * 0.98
                else: # Turning Left
                    self.abs_fl = speed_kmh * ratio_inner
                    self.abs_fr = speed_kmh * ratio_outer
                    self.abs_rl = speed_kmh * ratio_inner * 0.98
                    self.abs_rr = speed_kmh * ratio_outer * 0.98
            else:
                self.abs_fl = self.abs_fr = self.abs_rl = self.abs_rr = speed_kmh
            
            # Simulate ABS lockup reading if braking too hard
            if self.tcs_active and brake_input > 0.5:
                self.abs_fl *= random.uniform(0.8, 1.0)
                self.abs_fr *= random.uniform(0.8, 1.0)
            
            # Record OBD2 state
            self.obd_throttle = self.throttle_val
            self.obd_brake = brake_input
            if self.obd_airbag: self.obd_brake = 1.0
            self.obd_steer = self.steer_val
            
            self.obd_engine_load = min(100.0, (self.throttle_val * 80) + (self.rpm / 8000.0 * 20))
            self.obd_coolant_temp = min(90.0, self.obd_coolant_temp + dt * (self.rpm / 3000.0) * 0.1)
            self.obd_maf = (self.rpm * max(1.0, self.obd_engine_load)) / 2000.0
            self.obd_fuel_level = max(0.0, self.obd_fuel_level - dt * (max(1.0, self.obd_engine_load) / 10000.0))
            self.obd_intake_man_pressure = 30 + (self.obd_engine_load * 0.7)
            
            # Update Eco / Safety Score
            if abs(self.lon_g) > 0.6 or abs(self.lat_g) > 0.6 or self.tcs_active:
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
                airbag=self.obd_airbag,
                rpm=self.rpm,
                engine_load=self.obd_engine_load,
                coolant_temp=self.obd_coolant_temp,
                intake_air_temp=self.obd_intake_air_temp,
                maf_air_flow=self.obd_maf,
                fuel_level=self.obd_fuel_level,
                intake_man_pressure=self.obd_intake_man_pressure,
                sas_angle=self.sas_angle,
                abs_fl=self.abs_fl, abs_fr=self.abs_fr, abs_rl=self.abs_rl, abs_rr=self.abs_rr,
                tcs_active=self.tcs_active,
                latitude=getattr(self.bridge, 'gps_lat', 0.0) or 0.0,
                longitude=getattr(self.bridge, 'gps_lon', 0.0) or 0.0
            )
            state = self.sensor.get_state()
            
            event_id = self.rule_engine.evaluate(state, current_time)
            
            if self.obd_airbag:
                event_id = 4
                
            if pothole_detected:
                event_id = 5 # HAZARD
                if not hasattr(self, 'last_pothole_time') or (current_time - getattr(self, 'last_pothole_time')) > 2.0:
                    self.last_pothole_time = current_time
                    lat = getattr(self.bridge, 'gps_lat', None)
                    lon = getattr(self.bridge, 'gps_lon', None)
                    if lat and lon:
                        print(f"\n⚠️ [HAZARD DETECTED] POTHOLE LOGGED AT: {lat:.6f}, {lon:.6f}\n")
                    else:
                        print("\n⚠️ [HAZARD DETECTED] POTHOLE (Awaiting GPS Coordinates)\n")
                
            if self.emergency_mode:
                event_id = 8
            
            # Calculate Risk Engine first to get TTC Context
            highest_risk, min_ttc, trig_event = self.risk_engine.calculate_risk(state, simulated_distance=30.0)
            
            # ML Engine uses Temporal Sliding Window (10 frames) + TTC/Friction Context
            # Provide static dry friction of 1.0
            is_anomaly, ml_score = self.ml_engine.evaluate(state, min_ttc=min_ttc, friction=1.0)
            
            # Note: We still send the optimized lightweight packet over V2V radio (ESP32)
            self.seq += 1
            packet = VehicleStatePacket(
                self.vehicle_id, self.seq, current_time,
                noisy_speed, noisy_accel, self.heading,
                event=event_id, confidence=90,
                latitude=getattr(self.bridge, 'gps_lat', 0.0) or 0.0,
                longitude=getattr(self.bridge, 'gps_lon', 0.0) or 0.0
            )
            self.bridge.receive_packet(packet.to_json())
            
            self.update_ui(event_id, is_anomaly, ml_score, min_ttc)
            
            # --- Black Box Logging ---
            if event_id > 0 or (current_time - self.last_log_time) >= 1.0:
                self.last_log_time = current_time
                lat = getattr(self.bridge, 'gps_lat', None)
                lon = getattr(self.bridge, 'gps_lon', None)
                az = getattr(self.bridge, 'mpu_accel', [0,0,9.8])[2] if getattr(self.bridge, 'mpu_accel') else 9.8
                
                with open(self.log_filename, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        f"{lat:.6f}" if lat else "NO_LOCK",
                        f"{lon:.6f}" if lon else "NO_LOCK",
                        f"{self.speed * 3.6:.1f}",
                        f"{self.heading:.1f}",
                        f"{az:.2f}",
                        f"{self.roll:.1f}",
                        f"{self.pitch:.1f}",
                        event_id,
                        f"{self.eco_score:.1f}"
                    ])
            
            time.sleep(dt)

    def draw_graph(self):
        for line in self.graph_lines:
            self.canvas.delete(line)
        self.graph_lines.clear()
        
        if len(self.history_speed) < 2: return
        
        w = 600
        h = 120
        x_start = 600
        y_start = 560
        
        dx = w / len(self.history_speed)
        
        for i in range(1, len(self.history_speed)):
            x1 = x_start + (i-1)*dx
            y1 = y_start - (self.history_speed[i-1] / 200.0) * h
            x2 = x_start + i*dx
            y2 = y_start - (self.history_speed[i] / 200.0) * h
            l = self.canvas.create_line(x1, y1, x2, y2, fill="#10B981", width=3)
            self.graph_lines.append(l)

    def update_ui(self, event_id, is_anomaly, ml_score, ttc):
        speed_kmh = self.speed * 3.6
        
        def _update():
            # Speed Arc
            extent = min(240, (speed_kmh / 200.0) * 240)
            color = "#10B981" if speed_kmh < 120 else "#EF4444"
            self.canvas.itemconfig(self.speed_arc, extent=-extent, outline=color)
            self.canvas.itemconfig(self.speed_text, text=f"{speed_kmh:.0f}", fill=color)
            
            self.canvas.itemconfig(self.gear_text, text=f"G: {self.gear}")
            self.canvas.itemconfig(self.rpm_text, text=f"RPM: {int(self.rpm)}")
            
            score_col = "#10B981" if self.eco_score > 80 else ("#F59E0B" if self.eco_score > 40 else "#EF4444")
            self.canvas.itemconfig(self.eco_text, text=f"SAFETY SCORE: {int(self.eco_score)}", fill=score_col)
            
            # V2V Chassis Info
            tcs_str = "TCS/ABS: ACTIVE!" if self.tcs_active else "TCS/ABS: INACTIVE"
            tcs_col = "#EF4444" if self.tcs_active else "#10B981"
            self.canvas.itemconfig(self.tcs_text, text=tcs_str, fill=tcs_col)
            
            ttc_str = f"TTC: {ttc:.1f}s" if ttc < 100 else "TTC: SAFE"
            ttc_col = "#10B981" if ttc > 3.0 else "#EF4444"
            self.canvas.itemconfig(self.ttc_text, text=ttc_str, fill=ttc_col)
            
            self.canvas.itemconfig(self.roll_text, text=f"Roll: {int(self.roll)}° Pt: {int(self.pitch)}° (Lim: {int(self.rollover_limit)}°)")
            self.canvas.itemconfig(self.sas_text, text=f"SAS: {int(self.sas_angle)}°")
            
            # IMU Raw Update
            ax, ay, az = 0.0, 0.0, 0.0
            gx, gy, gz = 0.0, 0.0, 0.0
            if hasattr(self.bridge, 'mpu_accel') and self.bridge.mpu_accel:
                ax, ay, az = self.bridge.mpu_accel
            if hasattr(self.bridge, 'mpu_gyro') and self.bridge.mpu_gyro:
                gx, gy, gz = self.bridge.mpu_gyro
                
            self.canvas.itemconfig(self.accel_ui, text=f"X:{ax:4.1f} Y:{ay:4.1f} Z:{az:4.1f}")
            self.canvas.itemconfig(self.gyro_ui, text=f"X:{gx:4.1f} Y:{gy:4.1f} Z:{gz:4.1f}")
            
            # GPS Update
            if hasattr(self.bridge, 'gps_lat') and self.bridge.gps_lat is not None and self.bridge.gps_lon is not None:
                self.canvas.itemconfig(self.gps_ui, text=f"GPS: {self.bridge.gps_lat:.6f}, {self.bridge.gps_lon:.6f}", fill="#10B981")
                spd = getattr(self.bridge, 'gps_speed', 0.0)
                hdg = getattr(self.bridge, 'gps_heading', 0.0)
                sats = getattr(self.bridge, 'gps_sats', 0)
                self.canvas.itemconfig(self.gps_extra_ui, text=f"SPD: {spd:.1f} km/h  HDG: {hdg:.1f}°  SATS: {sats}", fill="#9CA3AF")
            else:
                status = getattr(self.bridge, 'gps_status', 'NO_LOCK')
                if status == 'NO_DATA':
                    self.canvas.itemconfig(self.gps_ui, text="GPS: WIRING FAULT (NO DATA)", fill="#EF4444") # Red
                    self.canvas.itemconfig(self.gps_extra_ui, text="Check TX/RX on GPIO 16/17", fill="#EF4444")
                else:
                    sats = getattr(self.bridge, 'gps_sats', 0)
                    self.canvas.itemconfig(self.gps_ui, text="GPS: AWAITING SATELLITE LOCK", fill="#3B82F6") # Blue
                    self.canvas.itemconfig(self.gps_extra_ui, text=f"Hardware connected. Satellites in view: {sats}", fill="#6B7280")
            
            # OBD2 UI Update (Restored)
            thr_pct = int(self.obd_throttle * 100)
            brk_pct = int(self.obd_brake * 100)
            
            self.canvas.itemconfig(self.obd_thr, text=f"THR: {thr_pct:02d}%", fill="#FCD34D" if thr_pct > 0 else "#9CA3AF")
            self.canvas.itemconfig(self.obd_brk, text=f"BRK: {brk_pct:02d}%", fill="#EF4444" if brk_pct > 0 else "#9CA3AF")
            
            if self.obd_airbag:
                self.canvas.itemconfig(self.obd_abg, text="ARBG: DEPLOYED", fill="#EF4444")
            else:
                self.canvas.itemconfig(self.obd_abg, text="ARBG: OK", fill="#10B981")
                
            self.canvas.itemconfig(self.obd_load_ui, text=f"LOD: {int(self.obd_engine_load):02d}%", fill="#9CA3AF")
            self.canvas.itemconfig(self.obd_cool_ui, text=f"ECT: {int(self.obd_coolant_temp):02d}°C", fill="#EF4444" if self.obd_coolant_temp > 95 else "#9CA3AF")
            self.canvas.itemconfig(self.obd_maf_ui, text=f"MAF: {int(self.obd_maf):02d}g/s", fill="#9CA3AF")
            
            # ABS 4-Wheel Speeds
            self.canvas.itemconfig(self.abs_fl_ui, text=f"FL: {self.abs_fl:5.1f}")
            self.canvas.itemconfig(self.abs_fr_ui, text=f"FR: {self.abs_fr:5.1f}")
            self.canvas.itemconfig(self.abs_rl_ui, text=f"RL: {self.abs_rl:5.1f}")
            self.canvas.itemconfig(self.abs_rr_ui, text=f"RR: {self.abs_rr:5.1f}")
            
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
                
            self.canvas.coords(self.bubble, bubble_x - 12, bubble_y - 12, bubble_x + 12, bubble_y + 12)
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
