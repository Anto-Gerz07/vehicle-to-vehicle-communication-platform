import json

class VehicleStatePacket:
    def __init__(self, vehicle_id, seq, timestamp, speed, acceleration, heading, event, confidence):
        self.vehicle_id = vehicle_id
        self.seq = seq
        self.timestamp = timestamp
        self.speed = speed
        self.acceleration = acceleration
        self.heading = heading
        self.event = event
        self.confidence = confidence

    def to_json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, data_str):
        data = json.loads(data_str)
        return cls(**data)

class V2VNetwork:
    def __init__(self):
        self.nodes = {}
        
    def register_node(self, node):
        self.nodes[node.vehicle_id] = node
        
    def broadcast(self, packet, sender_id):
        # Simulate ESP-NOW broadcast latency here if needed
        data_str = packet.to_json()
        for node_id, node in self.nodes.items():
            if node_id != sender_id:
                node.receive_packet(data_str)
