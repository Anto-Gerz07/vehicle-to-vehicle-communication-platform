import time

class SensorSim:
    def __init__(self, initial_speed=60.0):
        self.speed = initial_speed
        self.acceleration = 0.0
        self.heading = 0.0
        self.last_update = time.time()
        self.history = []

    def update(self, new_speed, new_acceleration, new_heading=0.0):
        self.speed = new_speed
        self.acceleration = new_acceleration
        self.heading = new_heading
        self.last_update = time.time()
        
        self.history.append({'speed': self.speed, 'accel': self.acceleration, 'time': self.last_update})
        if len(self.history) > 100:
            self.history.pop(0)

    def get_state(self):
        return {
            'speed': self.speed,
            'acceleration': self.acceleration,
            'heading': self.heading
        }
