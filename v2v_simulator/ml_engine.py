import numpy as np
import random
from collections import deque

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class MLEngine:
    def __init__(self):
        self.window_size = 10
        self.history = deque(maxlen=self.window_size)
        
        if SKLEARN_AVAILABLE:
            # We use a slightly higher contamination because the 70D space is sparse
            self.model = IsolationForest(contamination=0.02, random_state=42)
            self.is_fitted = True
            
            # Pre-train the model with a synthetic baseline of normal driving sequences
            baseline_data = []
            for _ in range(1000):
                sequence = []
                # Random starting state for the sequence
                base_speed = random.uniform(0.0, 35.0)
                base_accel = random.gauss(0.0, 1.0)
                base_ttc = random.uniform(5.0, 100.0) # Safe TTC
                base_fric = random.choice([0.1, 0.4, 0.8])
                
                for step in range(self.window_size):
                    # Slight variations per step to simulate continuous time
                    speed = max(0.0, base_speed + base_accel * 0.05 * step)
                    accel = base_accel + random.gauss(0, 0.1)
                    throttle = random.uniform(0.0, 0.4) if accel > 0 else 0.0
                    brake = random.uniform(0.0, 0.2) if accel < 0 else 0.0
                    steering = random.gauss(0.0, 0.1)
                    
                    # 7 Features per frame
                    sequence.extend([speed, accel, throttle, brake, steering, base_ttc, base_fric])
                    
                # 70 Features per sequence
                baseline_data.append(sequence)
                
            self.model.fit(baseline_data)
        else:
            self.model = None

    def evaluate(self, sensor_state, min_ttc=100.0, friction=0.8):
        if not SKLEARN_AVAILABLE:
            return False, 0.0
            
        # Hard Rule: If the airbag deployed, it's absolutely an anomaly!
        if sensor_state.get('airbag_deployed', False):
            return True, -1.0
            
        current_frame = [
            sensor_state.get('speed', 0.0),
            sensor_state.get('acceleration', 0.0),
            sensor_state.get('throttle', 0.0),
            sensor_state.get('brake', 0.0),
            sensor_state.get('steering', 0.0),
            min_ttc,
            friction
        ]
        
        self.history.append(current_frame)
        
        # We need a full window of 10 frames to evaluate
        if len(self.history) < self.window_size:
            return False, 0.0
            
        if self.is_fitted:
            # Flatten the deque into a single 70D vector
            flat_features = []
            for frame in self.history:
                flat_features.extend(frame)
                
            # 1 for normal, -1 for anomaly
            prediction = self.model.predict([flat_features])[0]
            is_anomaly = (prediction == -1)
            score = self.model.decision_function([flat_features])[0]
            return is_anomaly, score
        else:
            return False, 0.0
