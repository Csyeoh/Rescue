## Frontend Structure (rescue-ui)

- **Framework:** Next.js 15 (App Router)
- **Styling:** Tailwind CSS 4.0
- **Animations:** Framer Motion (motion)
- **Icons:** Lucide React
- **Components:**
  - `src/app`: Root layout and main entry point.
  - `src/components/Layout`: Core structural components (Header, Sidebar, Panels).
  - `src/components/Map`: Grid-based visualization for God View and Drone View.
  - `src/components/Drone`: Telemetry and status cards for individual drones.
  - `src/components/Config`: Mission parameters and environmental unknowns.
  - `src/components/UI`: Reusable UI primitives (Toasts, Buttons).
- **Hooks:**
  - `useMissionControl`: Centralized state and logic for mission lifecycle.
  - `useWebSocket`: Real-time telemetry updates from the simulation backend.

## Styling Guidelines

- **Typography:** Avoid excessive `uppercase`. Use `capitalize` or `font-medium` for headers and labels to maintain a professional, modern look.
- **Color Palette:**
  - Backgrounds: `mint-bg` (#f5fffa) for light mode, `neutral-dark` (#1A202C) for dark panels.
  - Accents: `azure-dark` (#416e6f) and `azure-mid` (#6aa7ad) for primary actions.
  - Status: `emerald-500` (Success), `alert-red` (#d65b34) (Error/Danger), `alert-orange` (#d96627) (Warning).
- **Interactions:** Use `framer-motion` for all panel transitions, hover states (`whileHover`), and click feedback (`whileTap`).
- **Layout:** Utilize flexible containers (`flex-1`, `min-h-0`) and dynamic sizing for panels like the Mission Log to ensure responsiveness.