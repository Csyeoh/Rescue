import time
import requests

BASE_URL = "http://127.0.0.1:8000"
MCP_URL = f"{BASE_URL}/api/mcp"


def generate_map(scenario="industrial", num_survivors=4, obstacle_difficulty="med"):
    payload = {
        "scenario": scenario,
        "num_survivors": num_survivors,
        "drone_battery": 100,
        "obstacle_difficulty": obstacle_difficulty,
    }
    r = requests.post(f"{BASE_URL}/api/generate_map", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    assert data.get("status") == "success", data
    return data["map_data"]


def start_mission(map_data, num_drones=3, drone_battery=100):
    payload = {
        "scenario": "industrial",
        "num_drones": num_drones,
        "drone_battery": drone_battery,
        "num_survivors": 4,
        "obstacle_difficulty": "med",
        "map_data": map_data,
    }
    r = requests.post(f"{BASE_URL}/api/start_mission", json=payload, timeout=30)
    r.raise_for_status()
    print("Mission start:", r.json())


def get_drones():
    r = requests.get(f"{MCP_URL}/drones", timeout=10)
    r.raise_for_status()
    return r.json()


def get_waypoint(drone_id):
    r = requests.get(f"{MCP_URL}/drone/{drone_id}/waypoints", timeout=10)
    r.raise_for_status()
    waypoints = r.json()
    if waypoints:
        return tuple(waypoints[0])
    return None


def step_towards(drone_id, tx, ty):
    r = requests.get(f"{MCP_URL}/drone/{drone_id}/step_towards", params={"tx": tx, "ty": ty}, timeout=10)
    r.raise_for_status()
    return r.json()


def get_pos(drone_id):
    r = requests.get(f"{MCP_URL}/drone/{drone_id}/pos", timeout=10)
    r.raise_for_status()
    return r.json()


def get_battery(drone_id):
    r = requests.get(f"{MCP_URL}/drone/{drone_id}/battery", timeout=10)
    r.raise_for_status()
    return r.json()


def submit_intent(drone_id, action, nx, ny, rationale, new_status="SEARCHING"):
    payload = {
        "drone_id": drone_id,
        "action": action,
        "target_x": int(nx),
        "target_y": int(ny),
        "rationale": rationale,
        "new_status": new_status,
    }
    r = requests.post(f"{MCP_URL}/intent", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    print("\n--- Generating Map ---")
    map_data = generate_map()

    print("\n--- Starting Mission ---")
    start_mission(map_data, num_drones=3)

    # Give backend a moment to initialize world and partition
    time.sleep(2)

    drones = get_drones()
    assert len(drones) >= 3, f"Expected at least 3 drones, got {drones}"
    drones = sorted(drones)[:3]
    print("Drones:", drones)

    # For each drone: pick a waypoint, compute one step, submit MOVE
    # Expect first N-1 submissions to be 'queued', final one 'applied_batch'
    statuses = []
    intents = []
    for i, d in enumerate(drones):
        wp = get_waypoint(d)
        if not wp:
            # Fallback: aim at (9,10+i) to guarantee an in-bounds move
            target = (9, 10 + i)
        else:
            target = wp
        step = step_towards(d, target[0], target[1])
        if "error" in step:
            print(f"step_towards error for {d}: {step}")
            # Fallback: stay put (9,9) to test batch but will not move
            step = {"x": 9, "y": 9, "already_at_target": False}
        nx, ny = step["x"], step["y"]
        res = submit_intent(d, "MOVE", nx, ny, rationale=f"{d} moving towards {target}")
        statuses.append(res.get("status"))
        intents.append((d, nx, ny, res))
        print(f"Submit {d}: {res}")

    # Validate batch logic
    assert statuses.count("queued") >= 2, f"Expected queued for first intents, got {statuses}"
    assert "applied_batch" in statuses, f"Expected final applied_batch, got {statuses}"

    # Verify positions and batteries updated for all drones
    for d, nx, ny, res in intents:
        pos = get_pos(d)
        batt = get_battery(d)
        print(f"{d} pos={pos} batt={batt}")
        assert "x" in pos and "y" in pos, f"Invalid pos for {d}: {pos}"
        # If move was valid, drone should now be at nx,ny
        if pos.get("x") != 9 or pos.get("y") != 9 or (nx, ny) != (9, 9):
            assert pos["x"] == nx and pos["y"] == ny, f"{d} did not move to intended cell: {pos} vs {(nx, ny)}"
        assert isinstance(batt, int) and batt <= 100, f"Battery not numeric for {d}: {batt}"

    print("\n✅ Batch intent application verified.")


if __name__ == "__main__":
    main()

