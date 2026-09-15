# AutoFlow AI — Frontend Technology Stack

**Purpose:** Define the technology stack required to build and run the AutoFlow AI desktop frontend as an Electron application.

**Scope:** Frontend and desktop shell only.

**Out of scope:** Backend, AI/ML runtime, execution engine, databases, real integrations, and production infrastructure.

---

## 1. Core Stack

| Layer | Technology | Purpose |
|---|---|---|
| Desktop Runtime | **Electron** | Runs the AutoFlow frontend as a native Windows desktop application |
| UI Framework | **Next.js** | React-based application framework |
| UI Library | **React** | Component-based interface |
| Language | **TypeScript** | Type-safe frontend development |
| Component System | **shadcn/ui** | Reusable UI components |
| Styling | **Tailwind CSS** | Utility-first styling |
| Icons | **Lucide React** | Consistent monochrome icon system |
| Package Manager | **pnpm** | Dependency and script management |
| State | **Zustand** or React state | Local UI/mock execution state |
| Validation | **Zod** | Frontend data/schema validation where useful |

---

## 2. Desktop Architecture

The Electron application should use the standard separation:

```text
Electron Main Process
        │
        ├── Window management
        ├── App lifecycle
        ├── Native desktop APIs
        └── Secure IPC
                 │
                 ▼
        Electron Preload
                 │
                 ▼
          Next.js Renderer
                 │
        ┌────────┴────────┐
        │                 │
     React UI          Local State
```

The renderer is responsible for the visual product experience.

The Electron main process is responsible for desktop-shell functionality.

Do not place core business logic or future workflow orchestration inside React components.

---

## 3. Next.js Configuration

Use the Next.js **App Router**.

Recommended frontend structure:

```text
desktop/
├── app/
│   ├── page.tsx
│   ├── tasks/
│   ├── agents/
│   ├── workflows/
│   ├── knowledge/
│   ├── files/
│   ├── approvals/
│   ├── executions/
│   └── settings/
│
├── components/
│   ├── layout/
│   ├── tasks/
│   ├── agents/
│   ├── workflows/
│   ├── knowledge/
│   ├── files/
│   ├── approvals/
│   ├── executions/
│   ├── shared/
│   └── ui/
│
├── electron/
│   ├── main.ts
│   ├── preload.ts
│   └── ipc/
│
├── lib/
│   ├── mock-data.ts
│   ├── types.ts
│   ├── constants.ts
│   └── utils.ts
│
├── public/
│   └── assets/
│
├── package.json
├── tsconfig.json
├── next.config.ts
├── postcss.config.mjs
├── components.json
└── README.md
```

---

## 4. shadcn/ui

Use shadcn/ui as the primary component foundation.

Expected components include:

```text
Button
Input
Textarea
Dialog
Sheet
Drawer
Dropdown Menu
Popover
Tooltip
Tabs
Card
Badge
Table
Command
Scroll Area
Separator
Skeleton
Avatar
Alert Dialog
Breadcrumb
Select
Checkbox
Switch
```

Do not create multiple visual styles for the same component.

The application should have one consistent design language.

---

## 5. Styling System

Use Tailwind CSS.

The design system is strictly monochrome.

Allowed visual values:

```text
Black
White
Neutral Gray
Near Black
Near White
```

Do not introduce product colors.

Avoid:

```text
Blue
Green
Red
Purple
Orange
Gradients
Colorful shadows
```

Status must use:

```text
icon
typography
border
opacity
fill contrast
```

rather than color.

---

## 6. Typography

Use a clean modern sans-serif for the interface.

Use monospace typography for technical identifiers:

```text
task_01HX...
exec_01HX...
agent_run_...
tool_call_...
```

Recommended hierarchy:

```text
Page title
Section heading
Card heading
Body
Metadata
Timestamp
Technical identifier
```

Typography should prioritize readability and information density.

---

## 7. Icons

Use **Lucide React**.

Icons should remain monochrome and consistent in:

```text
size
stroke width
alignment
visual weight
```

Do not mix several unrelated icon libraries.

---

## 8. State Management

Use local frontend state for the current phase.

Recommended approach:

```text
React state
+
Zustand where shared application state becomes useful
```

Example state:

```text
selectedWorkspace
selectedTask
selectedExecution
selectedGraphNode
taskStatus
agentStatus
approvalStatus
sidebarCollapsed
commandPaletteOpen
detailDrawerOpen
```

All data can come from:

```text
lib/mock-data.ts
```

The state layer should be written so a future backend API can replace the mock repository without rewriting the UI.

---

## 9. Mock Data Layer

No backend is required in this phase.

Use strongly typed mock data:

```text
workspaces
tasks
agents
workflows
executions
approvals
artifacts
knowledgeSources
files
timelineEvents
```

Keep mock data separate from presentation components.

Bad:

```text
TaskPage.tsx
  └── hard-coded task objects
```

Preferred:

```text
lib/mock-data.ts
        ↓
typed state
        ↓
TaskPage.tsx
```

---

## 10. Electron Main Process

Electron `main.ts` should handle:

```text
application startup
window creation
window lifecycle
development vs production loading
native menus where required
desktop-level events
secure IPC registration
```

The main process should not contain:

```text
AI agent logic
workflow planning
task orchestration
database logic
provider keys
business rules
```

---

## 11. Electron Preload

Use `preload.ts` as the controlled bridge between Electron and the renderer.

Expose only narrowly scoped APIs.

Conceptually:

```typescript
window.desktop = {
  app: {
    getVersion(): Promise<string>
  },
  window: {
    minimize(): void
    maximize(): void
    close(): void
  }
}
```

Do not expose raw Node.js or unrestricted Electron APIs to the renderer.

---

## 12. Electron Security Baseline

The desktop shell should follow a secure Electron configuration.

Use the equivalent of:

```text
contextIsolation = true
nodeIntegration = false
sandbox = true where compatible
```

The renderer must not receive unrestricted filesystem, shell, child-process, or Node.js access.

Native capabilities should be exposed through explicit preload APIs only.

---

## 13. Next.js + Electron Integration

The application should support two modes.

### Development

```text
Next.js dev server
        +
Electron
```

Electron loads the local Next.js development URL.

Conceptually:

```text
pnpm dev
    ↓
Next.js dev server
    ↓
Electron window
```

### Packaged Application

For the `.exe`:

```text
Next.js frontend
       ↓
production build/export strategy
       ↓
Electron
       ↓
Windows application package
```

The packaged Electron application should not require developers to manually start a Next.js development server.

---

## 14. Static Frontend Requirement

Because this phase is frontend-only, the desktop application should be capable of running with mock/local data without any external backend.

The packaged application should therefore provide:

```text
Electron
  +
frontend assets
  +
mock data
  +
local UI state
```

No external API should be required to open the interface.

---

## 15. Desktop Window

Initial desktop window target:

```text
Width: 1440
Height: 900
```

Minimum practical target:

```text
Width: 1280
Height: 800
```

The UI should support:

```text
resize
maximize
minimize
close
```

The primary experience is desktop-first.

---

## 16. Packaging

Use an Electron packaging/build solution such as:

```text
electron-builder
```

The primary packaging target is:

```text
Windows x64
```

The eventual artifact should be an installable Windows package such as:

```text
AutoFlow AI Setup.exe
```

and/or a portable Windows executable depending on release requirements.

---

## 17. Suggested Package Scripts

The frontend should expose a simple development workflow.

Conceptually:

```json
{
  "scripts": {
    "dev": "run next + electron",
    "next:dev": "next dev",
    "build": "next build",
    "electron:dev": "electron electron/main.ts",
    "typecheck": "tsc --noEmit",
    "lint": "next lint",
    "package:win": "electron-builder --win"
  }
}
```

The exact tooling for running multiple processes may use:

```text
concurrently
wait-on
cross-env
```

where useful.

---

## 18. Development Commands

The intended developer experience should be approximately:

```bash
pnpm install
pnpm dev
```

This should launch:

```text
Next.js
   ↓
Electron
   ↓
AutoFlow desktop UI
```

For a production package:

```bash
pnpm build
pnpm package:win
```

The exact command names can evolve, but the workflow should remain simple.

---

## 19. Environment Variables

Frontend configuration should remain minimal.

Example:

```text
NEXT_PUBLIC_APP_NAME
NEXT_PUBLIC_APP_VERSION
NEXT_PUBLIC_ENV
```

Do not put:

```text
LLM provider secrets
OAuth client secrets
database passwords
JWT signing secrets
connector credentials
backend master keys
```

into the renderer.

The future architecture explicitly keeps provider credentials outside the desktop renderer.

---

## 20. Backend Integration Placeholder

Although backend integration is out of scope now, keep a clean boundary for the future.

Suggested abstraction:

```text
components
    ↓
frontend service layer
    ↓
future API client
    ↓
backend
```

Do not let UI components directly depend on future network implementation.

For now:

```text
components
    ↓
mock repository
```

Later:

```text
components
    ↓
repository/service interface
    ↓
API client
    ↓
backend
```

---

## 21. Real-Time UI Placeholder

The eventual product will display live execution events.

For this phase, simulate these locally.

Mock event stream:

```text
task.created
task.planned
plan.validated
agent.started
tool.requested
tool.completed
observation.created
verification.passed
approval.requested
approval.granted
execution.completed
```

This allows the UI to be built against the same conceptual event model that the real backend will later provide.

---

## 22. Component Architecture

Recommended separation:

```text
Pages
  ↓
Feature Components
  ↓
Shared Components
  ↓
shadcn/ui
```

Example:

```text
TaskDetailPage
    ↓
TaskHeader
TaskGraph
LiveExecutionPanel
ExecutionTimeline
ArtifactPanel
ApprovalPanel
    ↓
Button / Card / Dialog / Badge / Tabs / ...
```

Avoid giant page components.

---

## 23. Quality Tooling

Recommended development tools:

```text
TypeScript
ESLint
Prettier
Git
```

Recommended checks:

```bash
pnpm typecheck
pnpm lint
pnpm build
```

Frontend tests can be added with:

```text
Vitest
React Testing Library
```

when component behavior becomes substantial.

---

## 24. Testing Scope

Frontend tests should focus on:

```text
navigation
task composer interactions
task graph rendering
agent state rendering
approval interactions
execution timeline
search
command palette
drawers
dialogs
responsive desktop behavior
component accessibility
```

Do not test backend behavior because the backend does not exist in this phase.

---

## 25. Build Separation

The repository should preserve this conceptual separation:

```text
desktop/
│
├── renderer
│     └── Next.js / React UI
│
├── electron
│     ├── main process
│     └── preload
│
└── local frontend state
```

Future architecture:

```text
Electron
   ↓
Backend API
   ↓
Control Plane
   ↓
AI/ML + Execution
```

The frontend must remain replaceable as a client.

---

## 26. What This Stack Produces

After this phase, the team should be able to run:

```bash
pnpm dev
```

and see the AutoFlow desktop application.

The application should provide:

```text
Dashboard
Tasks
Task detail
Task graph
Agents
Workflows
Knowledge
Files
Approvals
Executions
Settings
```

with realistic mock interactions.

Then:

```bash
pnpm package:win
```

should produce a Windows desktop package containing the frontend.

---

## 27. Explicit Non-Requirements

This technology stack does NOT require:

```text
FastAPI
PostgreSQL
Redis
Qdrant
LLM APIs
LangChain
LangGraph
OpenAI API
Gemini API
Groq API
NVIDIA API
Browser automation
Windows UI Automation
Real email providers
Cloud infrastructure
```

Those belong to the later AutoFlow platform layers.

The frontend should function independently.

---

## 28. Final Stack

The committed frontend direction is:

```text
                 AUTOFLOW DESKTOP
                        │
                    Electron
                        │
                ┌───────┴────────┐
                │                │
             Preload          Main Process
                │
                ▼
             Next.js
                │
              React
                │
          TypeScript
                │
        ┌───────┴─────────┐
        ▼                 ▼
     shadcn/ui        Tailwind CSS
        │
        ▼
   Lucide React
        │
        ▼
 Local Mock State
 (React / Zustand)
```

Packaging:

```text
Electron
   +
Next.js frontend
   +
Windows x64
   ↓
AutoFlow AI Setup.exe
```

---

# 29. Final Rule

For the current development phase:

> **Build the AutoFlow visual command center as a Next.js + React frontend running inside Electron, using shadcn/ui and Tailwind CSS with a strict black-and-white design system. Keep all data local/mock and keep the Electron shell secure and thin.**

The result should be a desktop `.exe` that looks like the eventual AutoFlow product while remaining completely independent of the backend and execution infrastructure.
