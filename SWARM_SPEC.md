# 🐝 SWARM_SPEC: Deterministic Routing & Reassignment Framework

This document defines the strict mathematical framework for the Swarm Commander's routing and dynamic workload reassignment. All coding agents must adhere to these formulas to ensure optimal search speed, drone utilization, and battery safety.

---

## 1. Dynamic Obstacle Tolerance & Battery Estimation

We use a dynamic multiplier ($O_M$) to account for the "Fog of War" (unknown obstacles) based on real-time discovery rates.

### **Formulas**
1.  **Laplace Smoothing (Obstacle Density):**
    $$Ratio_{Smoothed} = \frac{Total\_Discovered\_Obstacles + 2}{Total\_Explored\_Cells + 10}$$
2.  **Safety Gap:**
    $$Gap = 0.15 \times (1.0 - Ratio_{Smoothed})$$
3.  **Obstacle Multiplier ($O_M$):**
    $$O_M = 1.0 + Ratio_{Smoothed} + Gap$$
4.  **True Step Estimation:**
    $$Search\_Steps = N \times O_M$$
    *(Where $N$ is the number of unsearched cells in the claimed workload)*
5.  **Total Battery Cost:**
    $$Battery\_Cost = (D_{Commute} + Search\_Steps + D_{RTB}) \times 1.0$$
    *(Note: $1\%$ drain per step. We multiply by $1.0$ as a baseline, but the formula implies a $1:1$ ratio of steps to battery percentage)*
6.  **Dispatch Check:**
    A drone is only dispatched or assigned a workload if:
    $$Current\_Battery \ge Battery\_Cost + 10$$
    *(Ensuring a strict 10% reserve)*

---

## 2. Swarm Routing: Multi-Zone Assist (Drones at Base 9,9)

When a drone is at Base (9,9) and ready to deploy, it evaluates the global workload distribution.

### **Logic Flow**
1.  **Identify Targets:** Find drones with the largest ($B$) and second-largest ($C$) remaining workloads ($N_B, N_C$).
2.  **Target B (Primary Assist):**
    Calculate potential claim from B:
    $$N_{A1} = \frac{N_B - D_{A\_to\_B}}{2}$$
    *(If $N_{A1} \le 0$, the drone remains **IDLE**)*
3.  **Target C (Chain Evaluation):**
    Evaluate if the drone should chain Target B and Target C in one flight:
    - **Condition 1:** $D_{B\_to\_C} \le D_{A\_to\_B}$
    - **Condition 2:** $N_{C\_Remaining} = N_C - (D_{A\_to\_B} + N_{A1} + D_{B\_to\_C}) > 0$
    - **Condition 3:** Total battery check (using $O_M$ for both $N_{A1}$ and $N_{A2}$) passes the 10% reserve.
4.  **Decision:**
    - If **Chaining Passes**: Claim $N_{A1}$ from B and $N_{A2} = \frac{N_{C\_Remaining}}{2}$ from C.
    - Else: Claim only $N_{A1}$ from B.

---

## 3. IDLE State: "Pass-By" Charging Check (Drones in Field)

When a drone in the field finishes its queue and becomes IDLE, it must decide whether to assist another drone immediately or return to base to recharge.

### **Logic Flow**
1.  **Find Target:** Locate the largest remaining workload $N_{Target}$.
2.  **Calculate Claim:**
    $$N_{Claim} = \frac{N_{Target} - D_{Direct}}{2}$$
3.  **Direct Check:**
    Calculate $Battery\_Cost$ for a direct flight to $N_{Target}$ using $O_M$.
    - If $Current\_Battery \ge Battery\_Cost + 10$: **Go Direct**.
4.  **Detour Penalty (Recharge Check):**
    If the direct flight fails the battery check, calculate the detour cost:
    $$\Delta D = (D_{to\_Base} + D_{Base\_to\_Target}) - D_{Direct}$$
5.  **Decision:**
    - If $\Delta D \le 4$: Route to Base (9,9) for 100% recharge, then proceed to target.
    - If $\Delta D > 4$: Abandon claim and **RETURN_TO_BASE**.

---

## 🛠 Implementation Blueprint

### **Files to Modify/Create**

1.  **[zone_partitioner.py](file:///d%3A/Project/Rescue/rescue_swarm_sim/zone_partitioner.py)**
    - **Modify** `compute_rebalance`: Inject the **Multi-Zone Assist** and **Pass-By** logic.
    - **Add** `calculate_dynamic_battery_cost(drone_id, workload_size, commute_dist, rtb_dist)`: Implements the Laplace Smoothing and $O_M$ multiplier.
2.  **[mcp_server.py](file:///d%3A/Project/Rescue/rescue_swarm_sim/swarm_flow/crews/rescue_crew/mcp_server.py)**
    - **Add** `get_exploration_stats()`: Returns `total_discovered_obstacles` and `total_explored_cells` from the `answer_plane` table.
3.  **[http_tools.py](file:///d%3A/Project/Rescue/rescue_swarm_sim/swarm_flow/crews/rescue_crew/http_tools.py)**
    - **Add** `get_exploration_stats_tool`: CrewAI tool to fetch global stats.
4.  **[tasks.yaml](file:///d%3A/Project/Rescue/rescue_swarm_sim/swarm_flow/crews/rescue_crew/config/tasks.yaml)**
    - **Update** `searching_task`: Add instructions to check the "Pass-By" logic when waypoints are exhausted.
    - **Add** `rebalance_task`: A high-level task for the Commander to run the **Multi-Zone Assist** logic when drones are at base.

---

**CRITICAL:** The initial partitioning logic in `greedy_weighted_bfs` must remain untouched. These optimizations only apply to dynamic reassignments and IDLE state transitions.
