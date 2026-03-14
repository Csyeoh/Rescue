import sqlite3
conn = sqlite3.connect('swarm_state.db')
for row in conn.execute('SELECT timestamp, drone_id, message FROM logs ORDER BY id DESC LIMIT 50;'):
    print(row)
conn.close()
