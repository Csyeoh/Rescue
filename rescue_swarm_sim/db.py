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

    cursor.execute("""
        CREATE TABLE drones (
            id TEXT PRIMARY KEY,
            x REAL, y REAL, z REAL,
            battery INTEGER,
            status TEXT,
            is_destroyed INTEGER,
            task_queue TEXT,
            messages_for_commander TEXT,
            error_count INTEGER DEFAULT 0,
            thermal_memory TEXT
        )
    """)

    # Static terrain obstacles (impassable rubble/collapse)
    cursor.execute("""
        CREATE TABLE obstacles (
            id TEXT PRIMARY KEY,
            x REAL, y REAL,
            height REAL,
            discovered INTEGER DEFAULT 0
        )
    """)

    # Buildings (individual searchable tiles)
    cursor.execute("""
        CREATE TABLE buildings (
            id TEXT PRIMARY KEY,
            x REAL, y REAL,
            height REAL,
            revealed INTEGER DEFAULT 0
        )
    """)

    # Precomputed Building Clusters
    cursor.execute("""
        CREATE TABLE building_clusters (
            id TEXT PRIMARY KEY,
            cx REAL, cy REAL,
            revealed INTEGER DEFAULT 0,
            tile_count INTEGER,
            assigned_to TEXT DEFAULT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE survivors (
            id TEXT PRIMARY KEY,
            x REAL, y REAL,
            found INTEGER,
            found_tick INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE thermal_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cells_json TEXT,
            timestamp REAL
        )
    """)

    # Coverage Grid: 40x40 cells (0.5 unit res) covering 20x20 space
    cursor.execute("""
        CREATE TABLE coverage (
            x_idx INTEGER,
            y_idx INTEGER,
            revealed INTEGER DEFAULT 0,
            physical_visits INTEGER DEFAULT 0,
            thermal_scans INTEGER DEFAULT 0,
            PRIMARY KEY (x_idx, y_idx)
        )
    """)
    # Initialize grid
    cells = []
    for ix in range(40):
        for iy in range(40):
            cells.append((ix, iy, 0, 0, 0))
    cursor.executemany(
        "INSERT INTO coverage (x_idx, y_idx, revealed, physical_visits, thermal_scans) VALUES (?,?,?,?,?)",
        cells
    )

    cursor.execute("""
        CREATE TABLE mission_telemetry (
            tick INTEGER PRIMARY KEY,
            timestamp REAL,
            coverage_count INTEGER,
            found_survivors INTEGER,
            total_battery_consumed INTEGER
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
    drone_data:    [(id, x, y, z, battery, status, is_destroyed, task_queue, messages_for_commander, error_count, thermal_memory), ...]
    obstacle_data: [(id, x, y, height, discovered), ...]
    building_data: [(id, x, y, height, revealed), ...]
    building_cluster_data: [(id, cx, cy, revealed, tile_count, assigned_to), ...]
    survivor_data: [(id, x, y, found, found_tick), ...]
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        if drone_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO drones VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                drone_data
            )
        if obstacle_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO obstacles VALUES (?,?,?,?,?)",
                obstacle_data
            )
        if building_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO buildings VALUES (?,?,?,?,?)",
                building_data
            )
        if building_cluster_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO building_clusters VALUES (?,?,?,?,?,?)",
                building_cluster_data
            )
        if survivor_data:
            cursor.executemany(
                "INSERT OR REPLACE INTO survivors VALUES (?,?,?,?,?)",
                survivor_data
            )
        conn.commit()
    finally:
        conn.close()

def sync_coverage(revealed_indices):
    """
    revealed_indices: list of (ix, iy) tuples that are now revealed.
    """
    increment_physical_visits(revealed_indices)

def increment_physical_visits(cell_indices):
    """
    cell_indices: list of (ix, iy) tuples visited by passive vision (radius 1.0).
    Each call increments visit count by +1 per cell.
    """
    if not cell_indices:
        return
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.executemany(
            "UPDATE coverage SET revealed=1, physical_visits = physical_visits + 1 WHERE x_idx=? AND y_idx=?",
            cell_indices
        )
        conn.commit()
    finally:
        conn.close()

def increment_thermal_scans(cell_indices):
    """
    cell_indices: list of (ix, iy) tuples covered by an active thermal scan.
    Each call increments scan count by +1 per cell.
    """
    if not cell_indices:
        return
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.executemany(
            "UPDATE coverage SET thermal_scans = thermal_scans + 1 WHERE x_idx=? AND y_idx=?",
            cell_indices
        )
        conn.commit()
    finally:
        conn.close()

def get_revealed_coverage():
    """Returns list of (ix, iy) for all revealed cells."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT x_idx, y_idx FROM coverage WHERE revealed=1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def log_telemetry(tick, timestamp, total_battery_consumed):
    """Logs a snapshot of the mission state at a specific tick."""
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Calculate current coverage dynamically
        cursor.execute("SELECT COUNT(*) FROM coverage WHERE physical_visits > 0")
        coverage_count = cursor.fetchone()[0]

        # Calculate found survivors
        cursor.execute("SELECT COUNT(*) FROM survivors WHERE found=1")
        found_survivors = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO mission_telemetry (tick, timestamp, coverage_count, found_survivors, total_battery_consumed) VALUES (?,?,?,?,?)",
            (tick, timestamp, coverage_count, found_survivors, total_battery_consumed)
        )
        conn.commit()
    finally:
        conn.close()

def generate_mission_report():
    """Calculates AUC, MTTD, and other efficiency metrics from telemetry."""
    conn = get_db_conn()
    cursor = conn.cursor()
    
    # Fetch chronological telemetry
    cursor.execute("SELECT tick, coverage_count, found_survivors, total_battery_consumed FROM mission_telemetry ORDER BY tick ASC")
    telemetry = cursor.fetchall()

    if not telemetry:
        conn.close()
        return {"error": "No telemetry data available for report."}

    max_coverage = 1600 # 40x40 grid in continuous_space

    # Metric 1: Area Under the Curve (AUC) for Discovery
    # AUC = sum(coverage(t) * dt)
    auc = 0
    for i in range(1, len(telemetry)):
        prev_cov = telemetry[i-1][1]
        dt = telemetry[i][0] - telemetry[i-1][0] # Delta Tick
        auc += prev_cov * dt

    # Metric 2: Mean Time To Discovery (MTTD)
    discovery_ticks = []
    curr_surv = 0
    for row in telemetry:
        if row[2] > curr_surv: # A survivor was found!
            new_found = row[2] - curr_surv
            discovery_ticks.extend([row[0]] * new_found) # Log the tick it happened
            curr_surv = row[2]
            
    mttd = sum(discovery_ticks) / len(discovery_ticks) if discovery_ticks else 0

    # Final States
    final_tick = telemetry[-1][0]
    final_cov = telemetry[-1][1]
    final_surv = telemetry[-1][2]
    total_battery = telemetry[-1][3]

    # Energy Efficiency (Battery spent per cell revealed)
    energy_per_cell = round(total_battery / final_cov, 3) if final_cov > 0 else 0

    cursor.execute("SELECT COUNT(*) FROM coverage WHERE physical_visits > 0")
    physical_unique = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM coverage WHERE thermal_scans > 0")
    thermal_unique = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM coverage WHERE physical_visits > 0 AND thermal_scans > 0")
    overlap_unique = cursor.fetchone()[0]

    thermal_overlap_pct = round((overlap_unique / thermal_unique) * 100, 2) if thermal_unique > 0 else 0

    cursor.execute("SELECT COUNT(*) FROM coverage WHERE (physical_visits + thermal_scans) >= 3")
    severe_overlap_cells = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM survivors")
    total_survivors = cursor.fetchone()[0]

    cursor.execute(
        "SELECT x_idx, y_idx, physical_visits, thermal_scans FROM coverage WHERE physical_visits > 0 OR thermal_scans > 0"
    )
    coverage_stats = [
        {
            "x": r[0],
            "y": r[1],
            "physical_visits": r[2],
            "thermal_scans": r[3],
        }
        for r in cursor.fetchall()
    ]

    conn.close()

    return {
        "mission_duration_ticks": final_tick,
        "final_coverage": final_cov,
        "coverage_percentage": round((final_cov / max_coverage) * 100, 2),
        "survivors_found": final_surv,
        "total_survivors": total_survivors,
        "discovery_auc": auc,
        "mean_time_to_discovery": round(mttd, 2),
        "energy_efficiency": energy_per_cell,
        "physical_cells_unique": physical_unique,
        "thermal_cells_unique": thermal_unique,
        "overlap_cells_unique": overlap_unique,
        "thermal_overlap_pct": thermal_overlap_pct,
        "severe_overlap_cells": severe_overlap_cells,
        "coverage_stats": coverage_stats,
        "chart_data": [
            {"tick": row[0], "coverage": row[1], "survivors": row[2]} for row in telemetry
        ]
    }
