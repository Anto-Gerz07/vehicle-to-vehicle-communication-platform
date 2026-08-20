import re

with open('interactive_sim.py', 'r') as f:
    code = f.read()

# 1. Colors & Init State
code = code.replace('self.root.configure(bg="#0F0F13")', 'self.root.configure(bg="#090A0F")')

old_init = """        # Advanced Physics & Realism
        self.gear = 1
        self.rpm = 800
        self.road_conditions = ["DRY", "WET", "ICE"]
        self.road_idx = 0
        self.eco_score = 100.0"""
new_init = """        # Advanced Physics & Realism
        self.gear = 1
        self.rpm = 800
        self.road_conditions = ["DRY", "WET", "ICE"]
        self.road_idx = 0
        
        # Gamification
        self.combo_multiplier = 1.0
        self.total_score = 0.0
        self.shake_duration = 0
        self.shake_offset_x = 0
        self.shake_offset_y = 0"""
code = code.replace(old_init, new_init)

# 2. Physics loop gamification updates
old_eco = """            # Update Eco / Safety Score
            if abs(self.lon_g) > 0.6 or abs(self.lat_g) > 0.6:
                self.eco_score = max(0.0, self.eco_score - 1.0)
            elif self.obd_airbag:
                self.eco_score = 0.0
            else:
                self.eco_score = min(100.0, self.eco_score + 0.1)"""
new_eco = """            # Gamification Score Update
            if abs(self.lon_g) > 0.6 or abs(self.lat_g) > 0.6 or self.obd_airbag or self.obd_brake > 0.8:
                self.combo_multiplier = 1.0
                if self.obd_airbag:
                    self.shake_duration = 20
            else:
                self.combo_multiplier = min(5.0, self.combo_multiplier + dt * 0.1)
                
            self.total_score += (self.speed * self.combo_multiplier * dt)
            
            if self.shake_duration > 0:
                self.shake_duration -= 1
                self.shake_offset_x = __import__('random').randint(-10, 10)
                self.shake_offset_y = __import__('random').randint(-10, 10)
            else:
                self.shake_offset_x = 0
                self.shake_offset_y = 0"""
code = code.replace(old_eco, new_eco)

# 3. Setup UI
old_setup = """    def setup_ui(self):
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
        self.canvas.create_text(400, 590, text=controls, fill="#6B7280", font=("Helvetica", 14), justify=tk.CENTER)"""

new_setup = """    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, bg="#090A0F", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.font_title = ("Helvetica", 14, "bold")
        self.font_small = ("Helvetica", 12)
        self.font_mono = ("Courier", 12, "bold")
        
        self.c_panel = "#151821"
        self.c_border = "#2A2F3D"
        self.c_neon_cyan = "#00FFCC"
        self.c_neon_mag = "#FF0055"
        self.c_neon_grn = "#39FF14"
        self.c_dim = "#4B5563"
        
        # Dashboard Panel (Left)
        self.canvas.create_rectangle(20, 20, 380, 480, fill=self.c_panel, outline=self.c_border, width=2)
        
        # Gamified Arc Speedometer (Multiple Layers)
        self.canvas.create_arc(50, 50, 350, 350, start=150, extent=-120, outline=self.c_border, width=14, style=tk.ARC)
        self.canvas.create_arc(60, 60, 340, 340, start=150, extent=-120, outline="#1C212B", width=6, style=tk.ARC)
        
        self.speed_arc_glow = self.canvas.create_arc(50, 50, 350, 350, start=150, extent=0, outline=self.c_neon_cyan, width=14, style=tk.ARC)
        self.speed_arc = self.canvas.create_arc(60, 60, 340, 340, start=150, extent=0, outline="#FFFFFF", width=6, style=tk.ARC)
        
        self.speed_text = self.canvas.create_text(200, 200, text="0", fill=self.c_neon_cyan, font=("Helvetica", 68, "bold"))
        self.canvas.create_text(200, 250, text="KM/H", fill=self.c_dim, font=self.font_title)
        
        self.gear_text = self.canvas.create_text(130, 250, text="G: 1", fill="#FCD34D", font=self.font_title)
        self.rpm_text = self.canvas.create_text(270, 250, text="RPM: 800", fill="#FCD34D", font=self.font_title)
        
        # Score & Combo
        self.score_text = self.canvas.create_text(200, 290, text="SCORE: 0", fill=self.c_neon_grn, font=("Helvetica", 16, "bold"))
        self.combo_text = self.canvas.create_text(200, 320, text="COMBO: x1.0", fill=self.c_neon_mag, font=("Helvetica", 14, "bold"))
        
        # Status Box
        self.status_bg = self.canvas.create_rectangle(40, 360, 360, 420, fill="#2A2F3D", outline="")
        self.status_text = self.canvas.create_text(200, 390, text="STATUS: NORMAL", fill=self.c_neon_grn, font=self.font_title)
        self.ml_text = self.canvas.create_text(200, 450, text="ML Anomaly: False", fill=self.c_dim, font=self.font_small)
        
        # IMU & OBD2 Panel (Right Top)
        self.canvas.create_rectangle(400, 20, 780, 320, fill=self.c_panel, outline=self.c_border, width=2)
        
        self.imu_center_x, self.imu_center_y = 500, 150
        self.imu_radius = 90
        
        # Crosshairs and radar style for IMU
        self.canvas.create_oval(self.imu_center_x - self.imu_radius, self.imu_center_y - self.imu_radius,
                                self.imu_center_x + self.imu_radius, self.imu_center_y + self.imu_radius,
                                outline=self.c_neon_cyan, width=1, dash=(2, 4))
        self.canvas.create_line(self.imu_center_x - self.imu_radius, self.imu_center_y, self.imu_center_x + self.imu_radius, self.imu_center_y, fill=self.c_dim)
        self.canvas.create_line(self.imu_center_x, self.imu_center_y - self.imu_radius, self.imu_center_x, self.imu_center_y + self.imu_radius, fill=self.c_dim)
                                
        self.bubble_glow = self.canvas.create_oval(self.imu_center_x - 14, self.imu_center_y - 14,
                                              self.imu_center_x + 14, self.imu_center_y + 14,
                                              fill="", outline=self.c_neon_grn, width=2)
        self.bubble = self.canvas.create_oval(self.imu_center_x - 8, self.imu_center_y - 8,
                                              self.imu_center_x + 8, self.imu_center_y + 8,
                                              fill=self.c_neon_grn, outline="")
                                              
        self.road_text = self.canvas.create_text(680, 60, text="ROAD: DRY", fill="#E5E7EB", font=self.font_title)
        self.ttc_text = self.canvas.create_text(680, 100, text="TTC: SAFE", fill=self.c_neon_grn, font=self.font_title)
        self.roll_text = self.canvas.create_text(680, 140, text="Roll: 0°", fill="#E5E7EB", font=self.font_title)
        
        # OBD2 LIVE DATA BOX
        self.canvas.create_rectangle(420, 245, 760, 310, fill="#090A0F", outline=self.c_border)
        self.obd_thr = self.canvas.create_text(500, 265, text="THR: 00%", fill=self.c_dim, font=self.font_mono)
        self.obd_brk = self.canvas.create_text(500, 290, text="BRK: 00%", fill=self.c_dim, font=self.font_mono)
        self.obd_str = self.canvas.create_text(680, 265, text="STR:  00°", fill=self.c_dim, font=self.font_mono)
        self.obd_abg = self.canvas.create_text(680, 290, text="ARBG: OK", fill=self.c_neon_grn, font=self.font_mono)
        
        # Telemetry Graph (Bottom Right)
        self.canvas.create_rectangle(400, 340, 780, 480, fill=self.c_panel, outline=self.c_border, width=2)
        self.canvas.create_text(450, 360, text="LIVE TELEMETRY", fill=self.c_neon_cyan, font=self.font_small)
        
        # Grid for Graph
        for i in range(4):
            y = 380 + i*30
            self.canvas.create_line(420, y, 760, y, fill="#1C212B")
            
        self.graph_lines = []
        self.weather_particles = []
        
        # Warning Overlay
        self.warning_overlay = self.canvas.create_rectangle(0, 0, 1000, 700, fill="", outline="", width=0)
        
        # Controls Panel (Bottom)
        self.canvas.create_rectangle(20, 500, 780, 680, fill=self.c_panel, outline=self.c_border, width=2)
        controls = "CONTROLS:\n[Up/Down]: Drive/Brake    [Left/Right]: Steer\n[B]: Harsh Brake    [Space]: CRASH!\n[W]: Change Weather    [E]: Siren Mode"
        self.canvas.create_text(400, 590, text=controls, fill=self.c_dim, font=("Helvetica", 14), justify=tk.CENTER)"""
code = code.replace(old_setup, new_setup)

# 4. Update UI
old_update = """    def update_ui(self, event_id, is_anomaly, ml_score, ttc):
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
"""

new_update = """    def update_ui(self, event_id, is_anomaly, ml_score, ttc):
        speed_kmh = self.speed * 3.6
        
        def _update():
            # Apply Shake
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
            if self.shake_duration > 0:
                self.canvas.move(tk.ALL, self.shake_offset_x, self.shake_offset_y)
            else:
                # Reset position by ensuring no drift if needed, but Tkinter move is relative.
                # A safer way to shake is just offset window coords or use a static offset var,
                # actually let's just use move then move back.
                pass
                
            # Speed Arc
            extent = min(240, (speed_kmh / 160.0) * 240)
            color = self.c_neon_cyan if speed_kmh < 90 else self.c_neon_mag
            self.canvas.itemconfig(self.speed_arc_glow, extent=-extent, outline=color)
            self.canvas.itemconfig(self.speed_arc, extent=-extent)
            self.canvas.itemconfig(self.speed_text, text=f"{speed_kmh:.0f}", fill=color)
            
            self.canvas.itemconfig(self.gear_text, text=f"G: {self.gear}")
            self.canvas.itemconfig(self.rpm_text, text=f"RPM: {int(self.rpm)}")
            
            # Score & Combo
            self.canvas.itemconfig(self.score_text, text=f"SCORE: {int(self.total_score)}")
            combo_col = self.c_neon_cyan if self.combo_multiplier > 4.0 else (self.c_neon_grn if self.combo_multiplier > 2.0 else "#FCD34D")
            if self.combo_multiplier == 1.0: combo_col = self.c_dim
            self.canvas.itemconfig(self.combo_text, text=f"COMBO: x{self.combo_multiplier:.1f}", fill=combo_col)
            
            # Road & TTC
            cond = self.road_conditions[self.road_idx]
            cond_color = self.c_neon_cyan if cond == "WET" else "#E5E7EB"
            if cond == "ICE": cond_color = "#93C5FD"
            self.canvas.itemconfig(self.road_text, text=f"ROAD: {cond}", fill=cond_color)
            
            ttc_str = f"TTC: {ttc:.1f}s" if ttc < 100 else "TTC: SAFE"
            ttc_col = self.c_neon_grn if ttc > 3.0 else self.c_neon_mag
            self.canvas.itemconfig(self.ttc_text, text=ttc_str, fill=ttc_col)
            
            self.canvas.itemconfig(self.roll_text, text=f"Roll: {int(self.roll)}°")
            
            # OBD2 UI Update
            thr_pct = int(self.obd_throttle * 100)
            brk_pct = int(self.obd_brake * 100)
            steer_deg = int(self.obd_steer * 45)
            
            self.canvas.itemconfig(self.obd_thr, text=f"THR: {thr_pct:02d}%", fill="#FCD34D" if thr_pct > 0 else self.c_dim)
            self.canvas.itemconfig(self.obd_brk, text=f"BRK: {brk_pct:02d}%", fill=self.c_neon_mag if brk_pct > 0 else self.c_dim)
            self.canvas.itemconfig(self.obd_str, text=f"STR: {steer_deg:3d}°", fill=self.c_neon_cyan if abs(steer_deg) > 0 else self.c_dim)
            
            if self.obd_airbag:
                self.canvas.itemconfig(self.obd_abg, text="ARBG: DEPLOYED", fill=self.c_neon_mag)
            else:
                self.canvas.itemconfig(self.obd_abg, text="ARBG: OK", fill=self.c_neon_grn)
            
            # G-Force Bubble
            bubble_x = self.imu_center_x + (self.lat_g * self.imu_radius)
            bubble_y = self.imu_center_y - (self.lon_g * self.imu_radius)
            
            g_mag = math.hypot(self.lat_g, self.lon_g)
            b_color = self.c_neon_grn if g_mag < 0.3 else ("#FCD34D" if g_mag < 0.8 else self.c_neon_mag)
            
            dist = math.hypot(bubble_x - self.imu_center_x, bubble_y - self.imu_center_y)
            if dist > self.imu_radius:
                ratio = self.imu_radius / dist
                bubble_x = self.imu_center_x + (bubble_x - self.imu_center_x) * ratio
                bubble_y = self.imu_center_y + (bubble_y - self.imu_center_y) * ratio
                
            self.canvas.coords(self.bubble_glow, bubble_x - 14, bubble_y - 14, bubble_x + 14, bubble_y + 14)
            self.canvas.coords(self.bubble, bubble_x - 8, bubble_y - 8, bubble_x + 8, bubble_y + 8)
            self.canvas.itemconfig(self.bubble_glow, outline=b_color)
            self.canvas.itemconfig(self.bubble, fill=b_color)
            
            # Status
            status_text = EVENT_NAMES.get(event_id, "UNKNOWN").replace("_", " ")
            if self.obd_airbag: status_text = "CRASH / ROLLOVER!"
                
            is_warning = False
            if self.emergency_mode:
                flash = int(time.time() * 5) % 2 == 0
                self.canvas.itemconfig(self.status_bg, fill="#1E3A8A" if flash else "#7F1D1D")
                self.canvas.itemconfig(self.status_text, text="EMERGENCY SIREN", fill="#FFF")
                is_warning = flash
            elif event_id > 0:
                self.canvas.itemconfig(self.status_bg, fill="#7F1D1D")
                self.canvas.itemconfig(self.status_text, text=f"STATUS: {status_text}", fill="#FECACA")
                is_warning = True
            else:
                self.canvas.itemconfig(self.status_bg, fill="#2A2F3D")
                self.canvas.itemconfig(self.status_text, text="STATUS: NORMAL", fill=self.c_neon_grn)
                
            # Damage / Warning Overlay
            if is_warning or self.shake_duration > 0:
                self.canvas.itemconfig(self.warning_overlay, outline=self.c_neon_mag, width=10)
            else:
                self.canvas.itemconfig(self.warning_overlay, width=0)
                
            # ML Text
            ml_col = self.c_neon_mag if is_anomaly else self.c_dim
            self.canvas.itemconfig(self.ml_text, text=f"ML Anomaly: {is_anomaly} (Score: {ml_score:.2f})", fill=ml_col)
                
            self.draw_graph()
            self.draw_weather()
            
            if self.shake_duration > 0:
                # To prevent drifting, we move back immediately after drawing, but Tkinter drawing happens at idle.
                # Let's just adjust the root window geometry instead for shake, it's safer.
                pass
"""
code = code.replace(old_update, new_update)

# Fix window shake approach:
code = code.replace("""            if self.shake_duration > 0:
                # To prevent drifting, we move back immediately after drawing, but Tkinter drawing happens at idle.
                # Let's just adjust the root window geometry instead for shake, it's safer.
                pass""", """            if self.shake_duration > 0:
                x = self.root.winfo_x() + self.shake_offset_x
                y = self.root.winfo_y() + self.shake_offset_y
                self.root.geometry(f"1000x700+{x}+{y}")
""")

# Fix graph neon colors
old_draw_graph = """    def draw_graph(self):
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
            self.graph_lines.append(l)"""
            
new_draw_graph = """    def draw_graph(self):
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
            l = self.canvas.create_line(x1, y1, x2, y2, fill=self.c_neon_cyan, width=2)
            self.graph_lines.append(l)"""
code = code.replace(old_draw_graph, new_draw_graph)

with open('interactive_sim.py', 'w') as f:
    f.write(code)
print("Updated interactive_sim.py successfully.")
