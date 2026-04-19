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

    # Drones: float x/y, assigned_sector replaces assigned_cells
    cursor.execute("""
        CREATE TABLE drones (
            id TEXT PRIMARY KEY,
            x REAL, y REAL,
            battery INTEGER,
            status TEXT,
            is_destroyed INTEGER,
            thermal_memory TEXT,
            assigned_sector TEXT
        )
    """)

    # Static terrain obstacles (impassable rubble/collapse)
    cursor.execute("""
        CREATE TABLE obstacles (
            id TEXT PRIMARY KEY,
            x REAL, y REAL,
            discovered INTEGER DEFAULT 0
        )
    """)

    # Buildings (individual searchable tiles)
    cursor.execute("""
        CREATE TABLE buildings (
            id TEXT PRIMARY KEY,
            x REAL, y REAL,
            revealed INTEGER DEFAULT 0
        )
    """)

    # Precomputed Building Clusters
    cursor.execute("""
        CREATE TABLE building_clusters (
            id TEXT PRIMARY KEY,
            cx REAL, cy REAL,
            revealed INTEGER DEFAULT 0,
            tile_count INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE survivors (
            id TEXT PRIMARY KEY,
            x REAL, y REAL,
            found INTEGER
        )
    """)

    # Removing mission_state table as it is dynamically aggregated now

    cursor.execute("""
        CREATE TABLE thermal_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cells_json TEXT,
            timestamp REAL
        )
    """)

    conn.commit()
    conn.close()

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def sync_world_state(drone_data, obstacle_data, building_data, building_cluster_data, survivor_data):
    """
    Batch upsert for the entire simulation state.
    drone_data:    [(id, x, y, battery, status, is_destroyed, thermal_memory, assigned_sector), ...]
    obstacle_data: [(id, x, y, discovered), ...]
    building_data: [(id, x, y, revealed), ...]
    building_cluster_data: [(id, cx, cy, revealed, tile_count), ...]
    survivor_data: [(id, x, y, found), ...]
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        if drone_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO drones VALUES (?,?,?,?,?,?,?,?)",
                drone_data
            )
        if obstacle_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO obstacles VALUES (?,?,?,?)",
                obstacle_data
            )
        if building_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO buildings VALUES (?,?,?,?)",
                building_data
            )
        if building_cluster_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO building_clusters VALUES (?,?,?,?,?)",
                building_cluster_data
            )
        if survivor_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO survivors VALUES (?,?,?,?)",
                survivor_data
            )
        conn.commit()
    finally:
        conn.close()
