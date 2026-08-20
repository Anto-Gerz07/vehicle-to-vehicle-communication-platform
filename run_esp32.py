import time
from v2v_simulator.v2v_network import V2VNetwork
from v2v_simulator.main import VehicleNode
from v2v_simulator.serial_bridge import ESP32SerialBridge

def run_hardware_scenario(port='/dev/ttyUSB0'):
    # Initialize the network
    network = V2VNetwork()
    
    # Initialize the Serial Bridge to forward network packets to the ESP32
    # Adjust port as necessary (e.g., 'COM3' on Windows, '/dev/cu.usbserial...' on Mac)
    bridge = ESP32SerialBridge(network, port=port, baudrate=115200)
    
    # Create our simulated vehicles
    vehicle_a = VehicleNode("A", network, initial_speed=70.0) # Leading
    vehicle_b = VehicleNode("B", network, initial_speed=65.0) # Trailing
    
    print("\nStarting Hardware-in-the-Loop Simulation...")
    print("Watch your OLED screen!\n")
    time.sleep(2)
    
    # --- SCENARIO 1: Normal Driving ---
    print("--- SCENARIO 1: Normal Driving ---")
    current_time = time.time()
    vehicle_a.sensor.update(new_speed=70.0, new_acceleration=0.0)
    vehicle_b.sensor.update(new_speed=65.0, new_acceleration=0.0)
    vehicle_a.loop(current_time)
    vehicle_b.loop(current_time)
    time.sleep(3) # Wait to observe on OLED
    
    # --- SCENARIO 2: Hard Braking ---
    print("\n--- SCENARIO 2: Vehicle A Hard Braking ---")
    current_time = time.time()
    vehicle_a.sensor.update(new_speed=30.0, new_acceleration=-4.5)
    vehicle_b.sensor.update(new_speed=65.0, new_acceleration=0.0)
    vehicle_a.loop(current_time)
    vehicle_b.loop(current_time, simulated_distance=20.0)
    time.sleep(3)
    
    # --- SCENARIO 3: Accident/Collision ---
    print("\n--- SCENARIO 3: Accident Propagation ---")
    current_time = time.time()
    vehicle_a.sensor.update(new_speed=0.0, new_acceleration=-8.0)
    vehicle_b.sensor.update(new_speed=40.0, new_acceleration=-2.0)
    vehicle_a.loop(current_time)
    vehicle_b.loop(current_time, simulated_distance=30.0)
    
    print("\nSimulation complete. Closing bridge.")
    bridge.close()

if __name__ == '__main__':
    # You will need to change this to the actual port your ESP32 is on!
    # For Linux: '/dev/ttyUSB0' or '/dev/ttyACM0'
    # For Windows: 'COM3', 'COM4', etc.
    # For Mac: '/dev/cu.usbserial-0001'
    # 
    # Example: run_hardware_scenario(port='/dev/ttyUSB0')
    
    import sys
    port = '/dev/ttyUSB0' # Default
    if len(sys.argv) > 1:
        port = sys.argv[1]
        
    run_hardware_scenario(port)
