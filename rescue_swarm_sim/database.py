import sqlite3
import os
import time
import threading

DB_NAME = "swarm_state.db"
DB_TIMEOUT_S = 30.0
BUSY_TIMEOUT_MS = 30000
MAX_RETRIES = 8

# Module-level write lock: autopilot_tick and assign_drone_zone must both hold
# this before writing so they never contend for the SQLite writer slot.
DB_WRITE_LOCK = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT_S)
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return conn


def _with_retry(op):
    last_error = None
    for i in range(MAX_RETRIES):
        try:
            return op()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            last_error = e
            time.sleep(0.05 * (2**i))
    if last_error:
        raise last_error

def init_db():
    if os.path.exists(DB_NAME):
        # On Windows, the file may still be locked by a dying process.
        # Retry a few times before giving up.
        for attempt in range(5):
            try:
                os.remove(DB_NAME)
                break
            except PermissionError:
                if attempt < 4:
                    time.sleep(0.5)
                else:
                    # Last resort: rename it so we can still create a fresh one
                    try:
                        os.rename(DB_NAME, DB_NAME + ".bak")
                    except Exception:
                        pass  # If rename also fails, just proceed — SQLite will overwrite
        
    conn = _connect()
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
    
    # 2. QUESTION PLANE: Ground Truth Physics Engine (Simulation ONLY)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_plane (
            x INTEGER,
            y INTEGER,
            altitude REAL,
            is_obstacle INTEGER,
            terrain_type TEXT,
            PRIMARY KEY (x, y)
        )
    ''')
    
    # 2.1 ANSWER PLANE: The Discovered Map (AI & UI ONLY)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS answer_plane (
            x INTEGER,
            y INTEGER,
            altitude REAL,
            terrain_type TEXT,
            obstacle_discovered INTEGER DEFAULT 0,
            is_scanned INTEGER DEFAULT 0,
            PRIMARY KEY (x, y)
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
    
    # NEW table for bounding box assignments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drone_zones (
            drone_id TEXT PRIMARY KEY,
            x_min INTEGER,
            x_max INTEGER,
            y_min INTEGER,
            y_max INTEGER,
            is_complete INTEGER DEFAULT 0
        )
    ''')
    
    # NEW table for sequential waypoint routing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drone_waypoints (
            drone_id TEXT,
            seq INTEGER,
            x INTEGER,
            y INTEGER,
            is_done INTEGER DEFAULT 0,
            PRIMARY KEY (drone_id, seq)
        )
    ''')
    
    # NEW table for storing BFS zone weights statically
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cell_weights (
            x INTEGER,
            y INTEGER,
            weight INTEGER,
            PRIMARY KEY (x, y)
        )
    ''')
    
    conn.commit()
    conn.close()

def sync_terrain(terrain_data):
    """
    Called by the simulation at spawn.
    terrain_data format: (x, y, altitude, is_obstacle, terrain_type, obstacle_discovered)
    """
    def op():
        conn = _connect()
        try:
            cursor = conn.cursor()
            
            # Extract just what is needed for the two planes
            q_plane_data = [(r[0], r[1], r[2], r[3], r[4]) for r in terrain_data] 
            a_plane_data = [(r[0], r[1], r[2], r[4], r[5], 0) for r in terrain_data] # adding 0 for is_scanned
            
            # Ground truth gets EVERYTHING
            cursor.executemany('''
                INSERT OR REPLACE INTO question_plane (x, y, altitude, is_obstacle, terrain_type)
                VALUES (?, ?, ?, ?, ?)
            ''', q_plane_data)
            
            # Discovered map ONLY gets altitude and type (is_obstacle is stripped out!)
            # Once seeded, the simulation NEVER updates this table again. ONLY inserts missing rows!
            cursor.executemany('''
                INSERT OR IGNORE INTO answer_plane (x, y, altitude, terrain_type, obstacle_discovered, is_scanned)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', a_plane_data)
            
            conn.commit()
        finally:
            conn.close()
    return _with_retry(op)

def log_action(drone_id, message):
    def op():
        conn = _connect()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", (drone_id, message))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(op)
