import json
import time

import database

import agents
import ai_tools
import tasks

try:
    from crewai import Crew, Process
except Exception as e:  # pragma: no cover
    Crew = None
    Process = None
    _CREWAI_IMPORT_ERROR = e


def _log_system(message: str):
    try:
        database.log_action("SYSTEM", message)
    except Exception:
        pass


def _extract_text(result) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    raw = getattr(result, "raw", None)
    if isinstance(raw, str):
        return raw
    try:
        return str(result)
    except Exception:
        return ""


def run_swarm_commander():
    if Crew is None:
        raise RuntimeError(
            f"crewai is not installed or failed to import: {_CREWAI_IMPORT_ERROR}. "
            "Install with: pip install crewai"
        )

    terrain_analyst, swarm_commander = agents.build_agents()
    t1, t2 = tasks.build_tasks(terrain_analyst, swarm_commander)

    crew = Crew(
        agents=[terrain_analyst, swarm_commander],
        tasks=[t1, t2],
        process=Process.sequential,
        verbose=True,
    )

    _log_system("AI Swarm Commander online. Standing by for live mission state.")

    last_wait_log = 0.0

    while True:
        try:
            world = ai_tools.read_world_state()
            grid_ok = isinstance(world.get("grid"), list) and len(world["grid"]) > 0
            drones_ok = isinstance(world.get("drones"), list) and len(world["drones"]) > 0
            if not (grid_ok and drones_ok):
                now = time.time()
                if now - last_wait_log > 15:
                    _log_system("AI waiting: mission not initialized yet. Use the UI to DEPLOY SWARM.")
                    last_wait_log = now
                time.sleep(2)
                continue

            result = crew.kickoff()
            text = _extract_text(result)
            parsed = tasks.parse_json_or_none(text)
            if parsed and isinstance(parsed, dict):
                mission_lines = parsed.get("mission_log")
                if isinstance(mission_lines, list):
                    for line in mission_lines[-8:]:
                        if isinstance(line, str) and line.strip():
                            _log_system(f"AI: {line.strip()}")
                else:
                    _log_system("AI cycle complete.")
            else:
                compact = (text or "").strip().replace("\n", " ")
                if compact:
                    _log_system(f"AI output: {compact[:180]}")
        except Exception as e:
            _log_system(f"AI ERROR: {e}")
        time.sleep(2)


if __name__ == "__main__":
    run_swarm_commander()
