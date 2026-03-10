from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import database

# Initialize the API
app = FastAPI(title="Rescue Swarm API")

# Fix CORS so your Next.js frontend can fetch data without browser errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For a hackathon, allowing all origins is perfectly fine
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/state")
def get_world_state():
    """Returns the live state of the drones and survivors as JSON."""
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    
    # 1. Fetch live drone data
    cursor.execute("SELECT drone_id, x, y, battery FROM drones")
    drones_data = cursor.fetchall()
    drones = [
        {"id": row[0], "x": row[1], "y": row[2], "battery": row[3]} 
        for row in drones_data
    ]
    
    # 2. Fetch survivor data
    cursor.execute("SELECT survivor_id, x, y, is_discovered FROM survivors")
    survivors_data = cursor.fetchall()
    survivors = [
        {"id": row[0], "x": row[1], "y": row[2], "discovered": bool(row[3])} 
        for row in survivors_data
    ]
    
    # Fetch the 15 most recent logs
    cursor.execute("SELECT timestamp, drone_id, message FROM logs ORDER BY id DESC LIMIT 15")
    logs_data = cursor.fetchall()
    logs = [
        {"time": row[0], "drone": row[1], "message": row[2]} 
        for row in logs_data
    ]

    conn.close()
    
    # Return the exact JSON structure Next.js needs to map the grid
    return {
        "grid": {"width": 20, "height": 20},
        "drones": drones,
        "survivors": survivors,
        "logs": logs  # <-- Add this line
    }