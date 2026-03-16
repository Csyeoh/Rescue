import json
import time
import threading
import os

import database
import ai_tools
from autopilot import autopilot_tick

def _log_system(message: str):
    try:
        database.log_action("SYSTEM", message)
    except Exception:
        pass

# ─── Threading state ──────────────────────────────────────────────────────────

def run_swarm_commander():
    _log_system("Central Intelligence and Drone Autopilot online.")

    while True:
        try:
            # ── PHASE 1: Deterministic Autopilot (always runs, never blocked) ─
            autopilot_tick()

        except Exception as e:
            _log_system(f"Main Loop ERROR: {e}")

        time.sleep(1.0)

if __name__ == "__main__":
    run_swarm_commander()
