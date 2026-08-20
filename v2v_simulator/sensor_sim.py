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
        self.last_update = time.time()
        self.history = []

    def update(self, new_speed, new_acceleration, new_heading=0.0, throttle=0.0, brake=0.0, steering=0.0, airbag=False):
        self.speed = new_speed
        self.acceleration = new_acceleration
        self.heading = new_heading
        self.throttle = throttle
        self.brake = brake
        self.steering = steering
        self.airbag_deployed = airbag
        self.last_update = time.time()
        
        self.history.append({
            'speed': self.speed, 
            'accel': self.acceleration, 
            'throttle': self.throttle,
            'brake': self.brake,
            'steering': self.steering,
            'airbag': self.airbag_deployed,
            'time': self.last_update
        })
        if len(self.history) > 100:
            self.history.pop(0)

    def get_state(self):
        return {
            'speed': self.speed,
            'acceleration': self.acceleration,
            'heading': self.heading,
            'throttle': self.throttle,
            'brake': self.brake,
            'steering': self.steering,
            'airbag_deployed': self.airbag_deployed
        }
