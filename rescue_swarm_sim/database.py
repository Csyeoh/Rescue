import sqlite3

DB_NAME = "swarm_state.db"

def init_db():
    """Initializes the database schema for the simulation."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create Drones table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drones (
            drone_id TEXT PRIMARY KEY,
            x INTEGER,
            y INTEGER,
            battery INTEGER DEFAULT 100
        )
    ''')
    
    # Create Survivors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS survivors (
            survivor_id TEXT PRIMARY KEY,
            x INTEGER,
            y INTEGER,
            is_discovered BOOLEAN DEFAULT 0
        )
    ''')

    # Create Logs table for the Mission Log UI
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
            drone_id TEXT,
            message TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

# We will add the helper functions for "The Contract" (move_to, thermal_scan, etc.) here next.

# if __name__ == "__main__":
#     # Run this file directly to generate the swarm_state.db file
#     init_db()




def discover_drones() -> list[str]:
    """Returns a list of active drone IDs."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT drone_id FROM drones")
    drones = [row[0] for row in cursor.fetchall()]
    conn.close()
    return drones

def get_battery_status(drone_id: str) -> int:
    """Returns the current battery level of a drone from 0 to 100."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT battery FROM drones WHERE drone_id = ?", (drone_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def thermal_scan(drone_id: str) -> bool:
    """Checks the drone's current (x,y) against the hidden survivor database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Get the drone's current coordinates
    cursor.execute("SELECT x, y FROM drones WHERE drone_id = ?", (drone_id,))
    drone_loc = cursor.fetchone()
    
    if not drone_loc:
        conn.close()
        return False
        
    drone_x, drone_y = drone_loc
    
    # 2. Check if an undiscovered survivor is at these exact coordinates
    cursor.execute("SELECT survivor_id FROM survivors WHERE x = ? AND y = ? AND is_discovered = 0", (drone_x, drone_y))
    survivor = cursor.fetchone()
    
    if survivor:
        # 3. Mark the survivor as found
        cursor.execute("UPDATE survivors SET is_discovered = 1 WHERE survivor_id = ?", (survivor[0],))
        conn.commit()
        conn.close()
        return True
        
    conn.close()
    return False

def update_drone_state(drone_id: str, x: int, y: int, battery: int):
    """Internal helper for simulation.py to update the DB after a physical move."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE drones 
        SET x = ?, y = ?, battery = ? 
        WHERE drone_id = ?
    ''', (x, y, battery, drone_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    # 1. Set up the database (This creates swarm_state.db and the tables)
    init_db()

    # 2. Inject some dummy data for testing
    print("Injecting test data...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Clear out tables just in case you run this script multiple times
    cursor.execute("DELETE FROM drones")
    cursor.execute("DELETE FROM survivors")
    
    # Insert one drone at (5, 5) and one hidden survivor at (5, 5)
    cursor.execute("INSERT INTO drones (drone_id, x, y, battery) VALUES ('drone_alpha', 5, 5, 80)")
    cursor.execute("INSERT INTO survivors (survivor_id, x, y, is_discovered) VALUES ('survivor_1', 5, 5, 0)")
    
    conn.commit()
    conn.close()

    # 3. Run the tests
    print("\n=== RUNNING FUNCTION TESTS ===")
    
    # Test 1: Discover Drones
    print(f"Active Drones found: {discover_drones()}")
    
    # Test 2: Battery Status
    print(f"Battery of 'drone_alpha': {get_battery_status('drone_alpha')}%")
    
    # Test 3: Thermal Scan (First pass - should return True because they are both at 5,5)
    print(f"First Thermal Scan (Expect True): {thermal_scan('drone_alpha')}")
    
    # Test 4: Thermal Scan (Second pass - should return False because survivor is now marked 'discovered')
    print(f"Second Thermal Scan (Expect False): {thermal_scan('drone_alpha')}")
    
    print("==============================\n")

def log_action(drone_id: str, message: str):
    """Records an event to the mission log."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs (drone_id, message) VALUES (?, ?)", (drone_id, message))
    conn.commit()
    conn.close()