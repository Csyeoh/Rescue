import sqlite3
import os

DB_NAME = "swarm_state.db"

def init_db():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. DRONES TABLE (Upgraded with active and health status)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drones (
            drone_id TEXT PRIMARY KEY,
            x INTEGER,
            y INTEGER,
            battery INTEGER,
            is_active INTEGER,
            health_status TEXT
        )
    ''')
    
    # 2. GRID TABLE (Removed redundant water_level)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grid (
            x INTEGER,
            y INTEGER,
            altitude REAL,
            is_obstacle INTEGER,
            terrain_type TEXT,
            obstacle_discovered INTEGER,
            PRIMARY KEY (x, y)
        )
    ''')
    
    # 3. ENVIRONMENT TABLE (New!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS environment (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            global_water_level REAL,
            water_speed REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS survivors (
            survivor_id TEXT PRIMARY KEY,
            x INTEGER,
            y INTEGER,
            is_discovered INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            drone_id TEXT,
            message TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def sync_terrain(terrain_data):
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT OR REPLACE INTO grid (x, y, altitude, is_obstacle, terrain_type, obstacle_discovered)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', terrain_data)
    conn.commit()
    conn.close()

def update_environment(water_level, water_speed):
    """Saves the global water physics to the database."""
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO environment (id, global_water_level, water_speed)
        VALUES (1, ?, ?)
    ''', (water_level, water_speed))
    conn.commit()
    conn.close()

def update_drone_state(drone_id, x, y, battery):
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE drones SET x=?, y=?, battery=? WHERE drone_id=?", (x, y, battery, drone_id))
    conn.commit()
    conn.close()

def log_action(drone_id, message):
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", (drone_id, message))
    conn.commit()
    conn.close()