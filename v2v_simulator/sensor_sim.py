import time

class SensorSim:
    def __init__(self, initial_speed=60.0):
        self.speed = initial_speed
        self.acceleration = 0.0
        self.heading = 0.0
        self.throttle = 0.0
        self.brake = 0.0
        self.steering = 0.0
        self.airbag_deployed = False
        self.latitude = 0.0
        self.longitude = 0.0
        
        # Extended OBD2 Mode 01 PIDs
        self.rpm = 800
        self.engine_load = 0.0
        self.coolant_temp = 20.0
        self.intake_air_temp = 25.0
        self.maf_air_flow = 0.0
        self.fuel_level = 100.0
        self.intake_man_pressure = 100.0
        
        # V2V Chassis / Safety PIDs
        self.sas_angle = 0.0
        self.abs_fl = 0.0
        self.abs_fr = 0.0
        self.abs_rl = 0.0
        self.abs_rr = 0.0
        self.tcs_active = False
        
        self.last_update = time.time()
        self.history = []

    def update(self, new_speed, new_acceleration, new_heading=0.0, throttle=0.0, brake=0.0, steering=0.0, airbag=False,
               rpm=800, engine_load=0.0, coolant_temp=20.0, intake_air_temp=25.0, maf_air_flow=0.0, fuel_level=100.0, intake_man_pressure=100.0,
               sas_angle=0.0, abs_fl=0.0, abs_fr=0.0, abs_rl=0.0, abs_rr=0.0, tcs_active=False, latitude=0.0, longitude=0.0):
        self.speed = new_speed
        self.acceleration = new_acceleration
        self.heading = new_heading
        self.throttle = throttle
        self.brake = brake
        self.steering = steering
        self.airbag_deployed = airbag
        self.latitude = latitude
        self.longitude = longitude
        
        self.rpm = rpm
        self.engine_load = engine_load
        self.coolant_temp = coolant_temp
        self.intake_air_temp = intake_air_temp
        self.maf_air_flow = maf_air_flow
        self.fuel_level = fuel_level
        self.intake_man_pressure = intake_man_pressure
        
        self.sas_angle = sas_angle
        self.abs_fl = abs_fl
        self.abs_fr = abs_fr
        self.abs_rl = abs_rl
        self.abs_rr = abs_rr
        self.tcs_active = tcs_active
        
        self.last_update = time.time()
        
        self.history.append({
            'speed': self.speed, 
            'accel': self.acceleration, 
            'throttle': self.throttle,
            'brake': self.brake,
            'steering': self.steering,
            'airbag': self.airbag_deployed,
            'rpm': self.rpm,
            'engine_load': self.engine_load,
            'coolant_temp': self.coolant_temp,
            'maf_air_flow': self.maf_air_flow,
            'fuel_level': self.fuel_level,
            'tcs_active': self.tcs_active,
            'time': self.last_update
        })
        if len(self.history) > 100:
            self.history.pop(0)

    def get_state(self):
        return {
            'speed': self.speed,
            'acceleration': self.acceleration,
            'heading': self.heading,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'throttle': self.throttle,
            'brake': self.brake,
            'steering': self.steering,
            'airbag_deployed': self.airbag_deployed,
            'rpm': self.rpm,
            'engine_load': self.engine_load,
            'coolant_temp': self.coolant_temp,
            'intake_air_temp': self.intake_air_temp,
            'maf_air_flow': self.maf_air_flow,
            'fuel_level': self.fuel_level,
            'intake_man_pressure': self.intake_man_pressure,
            'sas_angle': self.sas_angle,
            'abs_fl': self.abs_fl,
            'abs_fr': self.abs_fr,
            'abs_rl': self.abs_rl,
            'abs_rr': self.abs_rr,
            'tcs_active': self.tcs_active
        }
