import requests
import time

print("Using hardcoded fallback map blueprint...")
map_data = {
    "topography": [{"center_x": 10, "center_y": 10, "base_altitude": 50.0, "spread": 20.0}],
    "buildings": [{"x": 5, "y": 5, "type": "single_story", "height": 4.0}],
    "survivors": [{"x": 5, "y": 5}, {"x": 5, "y": 5}, {"x": 5, "y": 5}]
}

print("Deploying swarm...")
res = requests.post("http://127.0.0.1:8000/api/start_mission", json={
    "scenario": "downtown",
    "obstacle_difficulty": "med",
    "drone_battery": 100,
    "num_survivors": 5,
    "map_data": map_data
})
print("Mission status:", res.json())
