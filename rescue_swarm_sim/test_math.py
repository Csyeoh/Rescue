# test_math.py
import ast
import types
from pathlib import Path

_ai_tools_path = Path(__file__).resolve().parent / "archive" / "ai_tools.py"
_source = _ai_tools_path.read_text(encoding="utf-8")
_tree = ast.parse(_source, filename=str(_ai_tools_path))

_needed = {
    "calculate_obstacle_multiplier",
    "calculate_true_battery_cost",
    "calculate_detour_penalty",
}
_funcs = [n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name in _needed]
if len(_funcs) != len(_needed):
    missing = sorted(list(_needed - {n.name for n in _funcs}))
    raise ImportError(f"Missing expected functions in {_ai_tools_path}: {missing}")

_module = ast.Module(body=_funcs, type_ignores=[])
_code = compile(_module, filename=str(_ai_tools_path), mode="exec")

ai_tools = types.SimpleNamespace()
exec(_code, ai_tools.__dict__)

print("--- Testing Phase 1 Math ---")

# 1. Test the Laplace Smoothing
# If we have explored 0 cells and found 0 obstacles...
mult = ai_tools.calculate_obstacle_multiplier(total_discovered=0, total_explored=0)
# Math check: Ratio = 2/10 (0.2). Gap = 0.15 * (1 - 0.2) = 0.12. Multiplier = 1.0 + 0.2 + 0.12 = 1.32
print(f"1. Obstacle Multiplier (0 explored, 0 discovered): {mult:.2f} (Expected: ~1.32)")

# 2. Test the Battery Cost
# 5 steps to get there, 10 cells to search, 5 steps to get home. Multiplier = 1.32
cost = ai_tools.calculate_true_battery_cost(d_commute=5, n_unsearched=10, d_rtb=5, multiplier=1.32)
# Math check: Search = 10 * 1.32 = 13.2. Total = (5 + 13.2 + 5) * 2 = 46.4
print(f"2. True Battery Cost: {cost} (Expected: ~46)")

# 3. Test the Detour Penalty
# Base is (9,9). Drone is at (5,9). Target is at (15,9).
# Direct is 10 steps. Detour to Base is 4 steps, Base to Target is 6 steps. Total = 10.
penalty = ai_tools.calculate_detour_penalty(current_pos=(5, 9), target_pos=(15, 9), base_pos=(9, 9))
print(f"3. Detour Penalty: {penalty} extra steps (Expected: 0)")

print("--- Tests Complete ---")
