import sqlite3
import time

conn = sqlite3.connect('swarm_state.db')
cursor = conn.cursor()

print("--- QUESTION PLANE (Ground Truth) ---")
try:
    cursor.execute("SELECT COUNT(*), SUM(is_obstacle) FROM question_plane")
    q_count, q_obs = cursor.fetchone()
    print(f"Total Grids: {q_count}, True Physical Obstacles: {q_obs}")
except Exception as e:
    print(e)
    
print("\n--- ANSWER PLANE (Known Map) ---")
try:
    cursor.execute("SELECT COUNT(*), SUM(obstacle_discovered) FROM answer_plane")
    a_count, a_obs = cursor.fetchone()
    print(f"Total Mapped Grids: {a_count}, Discovered Obstacles: {a_obs}")
    
    # Assert is_obstacle does not exist here
    try:
        cursor.execute("SELECT is_obstacle FROM answer_plane LIMIT 1")
        print("FAIL: is_obstacle maliciously exists in answer_plane!")
    except Exception:
        print("PASS: is_obstacle explicitly stripped from answer_plane.")
        
except Exception as e:
    print(e)

print("\n--- DRONE LOGS ---")
for row in cursor.execute('SELECT timestamp, drone_id, message FROM logs ORDER BY id DESC LIMIT 10;'):
    print(row)

conn.close()
