import sqlite3
import os
import json

DB_PATH = "live_state.db"

def init_db():
    if os.path.exists(DB_PATH):
        try: os.remove(DB_PATH)
        except: pass
    
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE drones (id TEXT PRIMARY KEY, x INTEGER, y INTEGER, battery INTEGER, status TEXT, is_destroyed INTEGER, thermal_memory TEXT, assigned_sector TEXT, target_x INTEGER, target_y INTEGER)")
    cursor.execute("CREATE TABLE cells (x INTEGER, y INTEGER, altitude REAL, building_height REAL, is_obstacle INTEGER, obstacle_discovered INTEGER, terrain_type TEXT, thermal_aura INTEGER, revealed INTEGER, assigned_to TEXT, PRIMARY KEY(x,y))")
    cursor.execute("CREATE TABLE survivors (id TEXT PRIMARY KEY, x INTEGER, y INTEGER, found INTEGER)")
    cursor.execute("CREATE TABLE mission_state (id INTEGER PRIMARY KEY, tick_count INTEGER, complete INTEGER, failed INTEGER, total_survivors INTEGER, found_survivors INTEGER)")
    cursor.execute("INSERT INTO mission_state (id, tick_count, complete, failed, total_survivors, found_survivors) VALUES (1, 0, 0, 0, 0, 0)")
    conn.commit()
    conn.close()

def get_db_conn():
    # If the file doesn't exist, this will create it
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    # Enable Write-Ahead Logging to allow concurrent read/writes (solves "database is locked" errors)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def sync_world_state(drone_data, cell_data, survivor_data, mission_data):
    """
    Performs a high-performance batch insert/update for the entire simulation state.
    """
    conn = get_db_conn()
    cursor = conn.cursor()
    
    try:
        # We wrap in a transaction implicitly by using executemany then commit
        if drone_data:
            cursor.executemany("INSERT OR REPLACE INTO drones VALUES (?,?,?,?,?,?,?,?,NULL,NULL)", drone_data)
        
        if cell_data:
            cursor.executemany("INSERT OR REPLACE INTO cells VALUES (?,?,?,?,?,?,?,?,?,?)", cell_data)
        
        if survivor_data:
            cursor.executemany("INSERT OR REPLACE INTO survivors VALUES (?,?,?,?)", survivor_data)
        
        if mission_data:
            cursor.execute("UPDATE mission_state SET tick_count=?, complete=?, failed=?, total_survivors=?, found_survivors=? WHERE id=1", mission_data)
            
        conn.commit()
    finally:
        conn.close()
