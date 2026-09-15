# AutoFlow AI — Desktop Command Center

> Turn one instruction into a verified workflow.

A polished, strictly monochrome **Windows desktop application** that is the
human-facing command center for AutoFlow AI. It runs in two modes: **mock mode**
(the default — every task, agent, workflow, execution, approval and artifact is
powered by local mock data and a client-side simulation engine, so it works with
zero backend) and **connected mode** (set `NEXT_PUBLIC_API_URL` to a running
Control Plane to render real planning, execution, verification, approvals and a
live SSE event stream). The same UI serves both; see **Connected mode** below.

## Stack

- **Electron** — secure desktop shell
- **Next.js (App Router)** + **React** + **TypeScript**
- **shadcn/ui** + **Tailwind CSS** + **Lucide** (monochrome)
- **Zustand** for shared UI + mock-domain state
- **pnpm** package manager

## Getting started

```bash
pnpm install
pnpm dev
```

`pnpm dev` runs the Next.js dev server and, once it is ready, launches Electron
pointed at `http://localhost:3000`.

> Run the frontend alone in a browser tab with `pnpm next:dev` and open
> `http://localhost:3000`.

## Production build

```bash
pnpm build
```

This produces:

- a fully static export of the frontend in `out/` (via `next build` with
  `output: export`), and
- the compiled Electron main/preload in `dist-electron/`.

Run the packaged experience locally (production mode, no dev server):

```bash
pnpm build
cross-env NODE_ENV=production electron .
```

Electron serves the static export through a custom, sandbox-friendly `app://`
protocol, so the app runs entirely offline with no Next.js server.

## Connected mode (live Control Plane)

By default the desktop runs on local mock data with a client-side simulation, so
it works with zero backend. To render **real** data from the AutoFlow Control
Plane — live task planning, execution, verification, approvals and an SSE event
stream — point it at a running backend. No page or component changes are needed;
the same seams (`lib/api`, `hooks/use-connected-task.ts`) light up when
`NEXT_PUBLIC_API_URL` is set.

### 1. Start the AI/ML mission server (optional, for real intelligence)

```bash
# from metamorph/ai-ml (its own venv)
.\.venv\Scripts\python.exe -c "from autoflow_ai.server.app import run_server; run_server(port=8770)"
```

### 2. Start the Control Plane backend

```bash
# from metamorph/backend (its own venv). INTEGRATION mode uses the AI/ML server;
# omit INTELLIGENCE_MODE to run the deterministic mock control plane instead.
$env:PYTHONPATH="."
$env:INTELLIGENCE_MODE="integration"     # or leave unset for mock
$env:AI_ML_URL="http://127.0.0.1:8770"
$env:RUN_INLINE_WORKER="true"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

### 3. Point the desktop at the backend

```bash
# desktop/.env  (copy from .env.example)
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_TOKEN=dev
```

Then `pnpm dev`. Creating a task from the composer now POSTs to the Control
Plane, the task detail view subscribes to the real SSE stream (with reconnect
replay), and approving a high-risk action resumes the real mission.

> Leaving `NEXT_PUBLIC_API_URL` empty returns the app to fully-local mock mode.

### Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Tasks still run the local simulation | `NEXT_PUBLIC_API_URL` is empty or unset — set it in `desktop/.env` and restart `pnpm dev`. |
| `Failed to fetch` / CORS errors | Backend not running on the configured URL, or origin not allowed. The backend allows `http://localhost:3000` and `app://.` by default. |
| Task reaches RUNNING but events show mock steps (`tool.started`) | The backend is in mock mode. Start it with `INTELLIGENCE_MODE=integration` **exactly** (case-insensitive, no `AUTOFLOW_` prefix). |
| Task never leaves QUEUED/PLANNING | No worker running. Start the backend with `RUN_INLINE_WORKER=true`, or run `python -m app.workers.task_worker` separately. |
| Approvals never complete after approve | Worker not processing the `resume_execution` job — same worker fix as above. |
| Live events don't stream | The SSE endpoint is `GET /api/v1/executions/{id}/stream`; confirm the backend is reachable and `sse-starlette` is installed. |

## Windows packaging

```bash
pnpm package:win        # NSIS installer + portable
pnpm package:portable   # portable .exe only
```

Output is written to `dist-win/`.

> **Note on the installer step.** Building the NSIS installer with
> `electron-builder` requires extracting its `winCodeSign` toolchain, which
> contains macOS symlinks. On Windows this needs **Developer Mode** or an
> **elevated (admin) shell** to create symlinks. Without those privileges the
> unpacked application (`dist-win/win-unpacked/AutoFlow AI.exe`) still builds
> and runs; only the `.exe` installer packaging step is blocked. Enable
> Developer Mode (Settings → Privacy & security → For developers) or run the
> packaging command from an elevated terminal to produce the installer.

## Project structure

```text
app/                    # Next.js App Router pages
  page.tsx              # dashboard / command center
  tasks/                # tasks list + [id] detail (graph, live, timeline)
  agents/               # agent directory + [id] profile
  workflows/            # reusable workflows + [id]
  knowledge/            # knowledge sources + [id]
  files/                # file browser + [id]
  approvals/            # approval queue (master/detail)
  executions/           # execution history + [id] console
  settings/             # settings (all local)

components/
  layout/               # AppShell, Sidebar, TopBar, CommandPalette, WorkspaceSelector
  tasks/ agents/ …      # feature components
  shared/               # StatusBadge, EmptyState, states, DetailDrawer, page primitives
  ui/                   # shadcn/ui primitives

electron/
  main.ts               # window mgmt, lifecycle, app:// protocol, secure IPC
  preload.ts            # narrow window.desktop bridge
  ipc/                  # (channel docs)

lib/
  types.ts              # domain model
  constants.ts          # status descriptors (monochrome), navigation
  repository.ts         # single data-access seam (swap for an API later)
  store.ts              # global UI + mock-domain store (Zustand)
  sim-store.ts          # mock execution player
  simulation.ts         # task creation + scripted execution frames
  mock-data/            # workspaces, agents, tasks, executions, approvals, …
```

## Design language

Strictly black / white / neutral grayscale. State is communicated through
glyphs, borders, opacity and typography — never through color. See
`app/globals.css` and `tailwind.config.ts` for the tokens.

## Architecture boundary

UI components depend only on the data-access seam, never on raw mock files. In
mock mode that seam is `lib/repository.ts` (local data + `lib/sim-store.ts`
simulation). In connected mode the same domain model is served over HTTP + SSE
by `lib/api` (`backendRepository`, `subscribeToExecutionEvents`) and fed into
the shared store by `hooks/use-connected-task.ts` — so pages render the store
identically in both modes. The Electron main process stays thin and holds no
business logic; the renderer never receives raw Node.js, filesystem, shell, or
child-process access.

## Scripts

| Script                 | Purpose                                    |
| ---------------------- | ------------------------------------------ |
| `pnpm dev`             | Next dev server + Electron                 |
| `pnpm next:dev`        | Frontend only (browser)                    |
| `pnpm build`           | Static export + compile Electron           |
| `pnpm typecheck`       | `tsc --noEmit`                             |
| `pnpm package:win`     | Windows installer + portable               |
| `pnpm package:portable`| Windows portable build                     |

Intelligence, verification and real execution live in the Control Plane
(`backend/`) and the AI/ML runtime (`ai-ml/`), not in the desktop. In mock mode
the desktop simulates them locally; in connected mode it renders their real
output. It never runs models or performs external actions itself.
