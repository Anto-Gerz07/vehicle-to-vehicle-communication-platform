import numpy as np
try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class MLEngine:
    def __init__(self):
        if SKLEARN_AVAILABLE:
            self.model = IsolationForest(contamination=0.05, random_state=42)
            self.is_fitted = False
            self.data_buffer = []
        else:
            self.model = None

    def evaluate(self, sensor_state):
        if not SKLEARN_AVAILABLE:
            return False, 0.0
            
        features = [sensor_state['speed'], sensor_state['acceleration']]
        self.data_buffer.append(features)
        
        # Fit on the fly if we have enough normal data
        if len(self.data_buffer) >= 50 and not self.is_fitted:
            self.model.fit(self.data_buffer)
            self.is_fitted = True
            
        if self.is_fitted:
            # Predict returns 1 for inliers, -1 for outliers
            prediction = self.model.predict([features])[0]
            is_anomaly = (prediction == -1)
            # Calculate a confidence score
            score = self.model.decision_function([features])[0]
            return is_anomaly, score
        else:
            return False, 0.0
