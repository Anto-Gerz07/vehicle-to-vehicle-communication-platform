import struct
import time
import serial

def pack_vehicle_state(packet):
    """
    Packs a VehicleStatePacket into a 15-byte compact binary struct.
    
    Format: < (little endian)
    c: char (1 byte) - Vehicle ID (e.g., 'A')
    H: unsigned short (2 bytes) - Seq
    I: unsigned int (4 bytes) - Timestamp (ms)
    h: signed short (2 bytes) - Speed * 100
    h: signed short (2 bytes) - Accel * 100
    h: signed short (2 bytes) - Heading
    B: unsigned char (1 byte) - Event
    B: unsigned char (1 byte) - Confidence
    Total: 15 bytes
    """
    fmt = '<cHIhhhBB'
    
    vid = str(packet.vehicle_id)[0].encode('ascii')
    seq_num = packet.seq & 0xFFFF
    ts = int(packet.timestamp * 1000) & 0xFFFFFFFF
    
    # Multiply by 100 to keep 2 decimal places of precision in an integer
    spd = int(packet.speed * 100)
    acc = int(packet.acceleration * 100)
    hdg = int(packet.heading)
    evt = int(packet.event)
    cnf = int(packet.confidence)
    
    return struct.pack(fmt, vid, seq_num, ts, spd, acc, hdg, evt, cnf)


class ESP32SerialBridge:
    """
    Acts as a node on the V2V network, listening for broadcasts
    and forwarding them over a serial connection to the ESP32.
    """
    def __init__(self, network, port='/dev/ttyUSB0', baudrate=115200):
        self.vehicle_id = "BRIDGE"
        self.network = network
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        
        # Register this bridge as a node on the simulation network
        if self.network:
            self.network.register_node(self)

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"[SerialBridge] Connected to ESP32 on {self.port} at {self.baudrate} baud.")
        except serial.SerialException as e:
            print(f"[SerialBridge] Warning: Could not open serial port {self.port}: {e}")
            print("[SerialBridge] Running without physical ESP32 connection (Dry run).")

    def receive_packet(self, data_str):
        from v2v_simulator.v2v_network import VehicleStatePacket
        
        # Deserialize JSON from simulation network back into a packet
        packet = VehicleStatePacket.from_json(data_str)
        
        # Pack to compact binary struct
        packed_data = pack_vehicle_state(packet)
        
        if self.ser and self.ser.is_open:
            try:
                # Optionally send a magic sync byte like 0xAA here if your ESP32 needs it
                # self.ser.write(b'\xAA')
                self.ser.write(packed_data)
            except Exception as e:
                print(f"[SerialBridge] Failed to write to serial: {e}")
        else:
            print(f"[SerialBridge] Would send {len(packed_data)} bytes for vehicle {packet.vehicle_id}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

if __name__ == "__main__":
    from v2v_simulator.v2v_network import V2VNetwork, VehicleStatePacket
    
    print("Testing Serial Bridge packing...")
    
    class DummyNetwork:
        def register_node(self, node): pass
    
    bridge = ESP32SerialBridge(DummyNetwork())
    
    packet = VehicleStatePacket(
        vehicle_id="A",
        seq=1,
        timestamp=time.time(),
        speed=65.2,
        acceleration=-1.5,
        heading=180,
        event=0, # NORMAL
        confidence=100
    )
    
    # Directly test the struct packing
    packed = pack_vehicle_state(packet)
    print(f"Packed size: {len(packed)} bytes")
    print(f"Hex dump: {packed.hex()}")
