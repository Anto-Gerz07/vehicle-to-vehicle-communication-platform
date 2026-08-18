import time
from v2v_simulator.sensor_sim import SensorSim
from v2v_simulator.rule_engine import RuleEngine, Event, EVENT_NAMES
from v2v_simulator.ml_engine import MLEngine
from v2v_simulator.v2v_network import V2VNetwork, VehicleStatePacket
from v2v_simulator.risk_engine import RiskEngine, RiskLevel
from v2v_simulator.oled_display import OLEDDisplay

class VehicleNode:
    def __init__(self, vehicle_id, network, initial_speed):
        self.vehicle_id = vehicle_id
        self.network = network
        self.sensor = SensorSim(initial_speed=initial_speed)
        self.rule_engine = RuleEngine()
        self.ml_engine = MLEngine()
        self.risk_engine = RiskEngine()
        self.display = OLEDDisplay()
        
        self.seq = 0
        self.network.register_node(self)

    def receive_packet(self, data_str):
        packet = VehicleStatePacket.from_json(data_str)
        self.risk_engine.update_neighbor(packet)

    def loop(self, current_time, simulated_distance=50.0):
        # 1. Get sensor data
        state = self.sensor.get_state()
        
        # 2. Local Event Detection
        event = self.rule_engine.evaluate(state, current_time)
        
        # 3. Optional ML Anomaly Detection (only if NORMAL from rules)
        confidence = 100
        if event == Event.NORMAL:
            is_anomaly, score = self.ml_engine.evaluate(state)
            if is_anomaly:
                event = Event.HAZARD
                confidence = 80 # lower confidence for ML
        
        # 4. V2V Broadcast
        self.seq += 1
        packet = VehicleStatePacket(
            self.vehicle_id, self.seq, current_time,
            state['speed'], state['acceleration'], state['heading'],
            event, confidence
        )
        self.network.broadcast(packet, self.vehicle_id)
        
        # 5. Risk Calculation
        risk, ttc, trigger_event = self.risk_engine.calculate_risk(state, simulated_distance)
        
        # 6. Update OLED Display
        neighbors_count = len(self.risk_engine.neighbor_table)
        print(f"\\n--- Vehicle {self.vehicle_id} Display ---")
        self.display.render(state['speed'], neighbors_count, risk, ttc, trigger_event)


def run_scenario():
    network = V2VNetwork()
    
    # Vehicle B (Trailing) at 65 km/h
    vehicle_b = VehicleNode("B", network, initial_speed=65.0)
    
    # Vehicle A (Leading) at 70 km/h
    vehicle_a = VehicleNode("A", network, initial_speed=70.0)
    
    print("Initializing Simulation Scenario...")
    time.sleep(1)
    
    # ---------------------------------------------
    # Scenario 1: Normal Driving
    # ---------------------------------------------
    print("\\n=================================================")
    print("=== SCENARIO 1: Normal Driving               ===")
    print("=================================================")
    current_time = time.time()
    vehicle_a.sensor.update(new_speed=70.0, new_acceleration=0.0)
    vehicle_b.sensor.update(new_speed=65.0, new_acceleration=0.0)
    
    # Run nodes
    vehicle_a.loop(current_time)
    vehicle_b.loop(current_time)
    
    time.sleep(1.5)
    
    # ---------------------------------------------
    # Scenario 2: Harsh Braking by Vehicle A
    # ---------------------------------------------
    print("\\n=================================================")
    print("=== SCENARIO 2: Vehicle A Harsh Braking      ===")
    print("=================================================")
    current_time = time.time()
    # Vehicle A drops speed and has large negative acceleration
    vehicle_a.sensor.update(new_speed=30.0, new_acceleration=-4.5)
    # Vehicle B maintains speed
    vehicle_b.sensor.update(new_speed=65.0, new_acceleration=0.0)
    
    # Vehicle A detects braking and broadcasts
    vehicle_a.loop(current_time)
    # Vehicle B receives packet, calculates high closing speed and TTC, displays warning
    # Distance is shrinking rapidly. Closing speed = (65 - 30) = 35km/h = ~9.7m/s. TTC with 20m distance = ~2.06s
    vehicle_b.loop(current_time, simulated_distance=20.0)
    
    time.sleep(1.5)
    
    # ---------------------------------------------
    # Scenario 3: Accident Propagation
    # ---------------------------------------------
    print("\\n=================================================")
    print("=== SCENARIO 3: Accident Propagation         ===")
    print("=================================================")
    current_time = time.time()
    # Vehicle A crashes (speed to 0, massive decel)
    vehicle_a.sensor.update(new_speed=0.0, new_acceleration=-8.0)
    # Vehicle B also slows down in response
    vehicle_b.sensor.update(new_speed=40.0, new_acceleration=-2.0)
    
    # Vehicle A loops and sends ACCIDENT
    vehicle_a.loop(current_time)
    # Vehicle B loops and shows ACCIDENT warning
    vehicle_b.loop(current_time, simulated_distance=30.0)
    
if __name__ == '__main__':
    run_scenario()
