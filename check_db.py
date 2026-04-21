import sqlite3
import json

def check_drones():
    conn = sqlite3.connect('rescue_swarm_sim/live_state.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, x, y, status, assigned_sector FROM drones WHERE id IN ('drone_1', 'drone_2', 'drone_3');")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, X: {row[1]}, Y: {row[2]}, Status: {row[3]}, Sector: {row[4]}")
    conn.close()

if __name__ == "__main__":
    check_drones()
