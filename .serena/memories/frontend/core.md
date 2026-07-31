# AegisWiFi — Frontend state

## Current state
- `frontend/index.html` — basic HTML shell
- `frontend/vite.config.ts` — Vite configuration (React + TypeScript)
- No `package.json`, no `node_modules/`, no `src/` directory
- No React components, pages, stores, API layer, hooks, or types
- Frontend is entirely a skeleton — nothing renders beyond the HTML shell

## Planned stack (from minuta §9.2)
React, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Router, Recharts, WebSocket, Zod

## Planned pages (from minuta §32)
Dashboard, Engagements, Live Scan (AP + clients), Network Detail, Handshakes, Cracking Jobs, Findings, Reports

## To deliver MVP frontend
- Initialize npm project with Vite + React + TS
- Set up Tailwind CSS
- Set up TanStack Query, Zustand, React Router, Zod
- Implement all 8 page types from §32
- API client layer against FastAPI backend
- WebSocket integration for live scan and job progress
- Responsive dark-themed design (auditor tool aesthetic)