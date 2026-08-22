class Event:
    NORMAL = 0
    OVERSPEED = 1
    LOSS_OF_TRACTION = 2
    SUDDEN_SLOWDOWN = 3
    ACCIDENT = 4
    HAZARD = 5
    EMERGENCY_STOP = 6
    COLLISION_WARNING = 7
    EMERGENCY_VEHICLE = 8
    HARSH_BRAKING = 9

EVENT_NAMES = {v: k for k, v in Event.__dict__.items() if not k.startswith('_')}

class RuleEngine:
    def __init__(self, speed_limit=60.0):
        self.speed_limit = speed_limit
        self.last_speed = None
        self.last_time = None

    def evaluate(self, sensor_state, current_time):
        speed = sensor_state['speed']
        accel = sensor_state['acceleration']
        
        event = Event.NORMAL
        
        if accel <= -5.0 and speed <= 5.0:
            event = Event.ACCIDENT
        elif accel < -3.0:
            event = Event.HARSH_BRAKING
        elif sensor_state.get('tcs_active', False):
            event = Event.LOSS_OF_TRACTION
        elif self.last_speed is not None and (self.last_speed - speed) > 20 and (current_time - self.last_time) < 2.0:
            event = Event.SUDDEN_SLOWDOWN
        elif speed > self.speed_limit:
            event = Event.OVERSPEED
            
        self.last_speed = speed
        self.last_time = current_time
        
        return event
