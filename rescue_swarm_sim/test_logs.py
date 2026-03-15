import sqlite3
import mcp_server
print(mcp_server.thermal_scan('drone_1'))
conn = sqlite3.connect('swarm_state.db')
print('Discovered Survivors:', conn.cursor().execute("SELECT SUM(is_discovered) FROM survivors").fetchone()[0])
