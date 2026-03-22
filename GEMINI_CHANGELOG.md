# GEMINI_CHANGELOG

## [2026-03-22]

### GEMINI.md
- Added frontend structure and styling documentation.

### globals.css
- Refined theme variables and base styles.
- Added custom scrollbar and resize handle styles.
- Standardized typography and palette.

### App Layout (src/app/page.tsx)
- Implemented log height state and resizability logic.
- Added smooth view transitions with `AnimatePresence`.
- Refactored ConfigPage to be full-page and animated.

### Configuration Page (src/components/Config/ConfigPage.tsx)
- Redesigned as a full-page dashboard layout.
- Removed excessive uppercase and improved grouping of parameters.
- Added motion transitions and full-screen responsive layout.

### Mission Log Panel (src/components/MissionLog/MissionLogPanel.tsx)
- Implemented a draggable resize handle at the top.
- Used `framer-motion` for log entry animations.
- Refined typography and spacing for better readability.

### Layout Components (src/components/Layout/*)
- **Header:** Softened styling, added motion progress bars, and removed excessive uppercase.
- **SidebarConfig:** Improved button interactions and parameter grouping.
- **SwarmStatusPanel:** Implemented smooth expansion/collapse with `framer-motion`.

### Drone Components (src/components/Drone/DroneCard.tsx)
- Enhanced telemetry visualization with smoother battery/status transitions.
- Added `framer-motion` layout animations.

### Map Components (src/components/Map/*)
- **GridCell:** Refined tooltips and indicator animations.
- **MapContainer:** Cleaned up headers and legend with modern styling.

### Map Generation (rescue_swarm_sim/prompts/map_builder.py)
- Overhauled `MAP_BUILDER_PROMPT` with Expert Urban Planner logic.
- Implemented sparse distribution targets (15-25% coverage).
- Added explicit road network/corridor requirements for structured layouts.
- Defined scenario-specific placement rules (Avenues for Downtown, Yards for Suburban).
- Added "Mountain Outpost" scenario focused on topographic alignment.

### UI & Logic (rescue-ui)
- Integrated "Mountain Outpost" into `ConfigPage`.
- Updated `useMissionControl` to support the new scenario in random generation.
