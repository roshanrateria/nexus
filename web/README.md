# Nexus — web console

Liquid-glass dashboard for the Lumen ("Nexus") autonomous browser agent.
Dark theme default, light toggle; demo replay needs no backend.

## Run

```bash
cd web
npm install
npm run dev            # http://localhost:3000
```

- Live mode: point dev mode at the Python agent's API server (its own page
  serves the built export instead):

  ```bash
  NEXT_PUBLIC_NEXUS_URL=http://127.0.0.1:8765 npm run dev
  ```

- Demo mode: <http://localhost:3000/?demo=1> — replays a scripted 40 s run
  (plan, review-escalation, verified evidence, streamed report) through the
  exact store/commit path used by live SSE. No Python needed.

Production: `python scripts/build_ui.py` (runs `npm ci && npm run build`),
then `runner.py` serves `web/out` at `/` — API and UI from one process, so
this base URL stays empty (same origin) in static exports.

Production check:

```bash
npm run build
npm run lint
```
