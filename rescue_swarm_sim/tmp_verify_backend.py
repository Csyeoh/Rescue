import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_mission():
    print(f"--- Generating Map ---")
    map_config = {
        "scenario": "industrial",
        "num_drones": 3,
        "drone_battery": 100,
        "num_survivors": 5,
        "obstacle_difficulty": "med"
    }
    resp = requests.post(f"{BASE_URL}/api/generate_map", json=map_config)
    print(f"Map Resp: {resp.status_code} - {resp.text[:200]}")
    
    if resp.status_code != 200:
        return
        
    map_data = resp.json().get("map_data")
    
    print(f"\n--- Starting Mission ---")
    mission_config = {**map_config, "map_data": map_data}
    resp = requests.post(f"{BASE_URL}/api/start_mission", json=mission_config)
    print(f"Mission Resp: {resp.status_code} - {resp.text[:200]}")
    
    if resp.status_code == 200:
        print("\n--- Waiting for 30s to observe backend logs ---")
        time.sleep(30)
        
        print("\n--- Checking Drone Telemetry ---")
        # In this sim, drones are just agents in the world
        # We can check via the simulation global if accessible, 
        # but let's just look at the backend output.
        pass

if __name__ == "__main__":
    test_mission()
