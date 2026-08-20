import re

with open('interactive_sim.py', 'r') as f:
    code = f.read()

# Replace setup_ui
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
        
code = re.sub(r'    def setup_ui\(self\):.*?    def bind_keys', new_setup + '\n\n    def bind_keys', code, flags=re.DOTALL)

with open('interactive_sim.py', 'w') as f:
    f.write(code)
print("Regex replace applied.")
