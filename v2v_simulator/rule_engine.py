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
        
        # [Item 6] Event Hysteresis
        self.current_event = Event.NORMAL
        self.event_start_time = 0
        self.hold_duration = 1.5 # seconds

    def evaluate(self, sensor_state, current_time):
        speed = sensor_state['speed']
        accel = sensor_state['acceleration']
        
        raw_event = Event.NORMAL
        
        if accel <= -5.0 and speed <= 5.0:
            raw_event = Event.ACCIDENT
        elif accel < -3.0:
            raw_event = Event.HARSH_BRAKING
        elif sensor_state.get('tcs_active', False):
            raw_event = Event.LOSS_OF_TRACTION
        elif self.last_speed is not None and (self.last_speed - speed) > 20 and (current_time - self.last_time) < 2.0:
            raw_event = Event.SUDDEN_SLOWDOWN
        elif speed > self.speed_limit:
            raw_event = Event.OVERSPEED
            
        # Hysteresis Logic
        if raw_event != Event.NORMAL and raw_event >= self.current_event:
            # Upgrade or maintain a non-normal event
            self.current_event = raw_event
            self.event_start_time = current_time
        elif self.current_event != Event.NORMAL:
            # Downgrade only if hold duration has passed
            if current_time - self.event_start_time > self.hold_duration:
                self.current_event = raw_event
        else:
            self.current_event = raw_event
            
        self.last_speed = speed
        self.last_time = current_time
        
        return self.current_event
