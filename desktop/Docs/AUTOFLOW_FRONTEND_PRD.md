# AutoFlow AI — Frontend Design PRD

**Status:** Frontend-only design specification  
**Scope:** UI/UX and frontend implementation only  
**Product:** AutoFlow AI  
**Frontend Stack:** Next.js + React + TypeScript + shadcn/ui + Tailwind CSS  
**Visual Direction:** Strict black-and-white / monochrome  
**Platform Target:** Desktop-first experience  
**Backend / AI / Execution:** Out of scope for this phase  

---

## 1. Purpose

This document defines the frontend-only product requirements for the first AutoFlow AI desktop experience.

The goal is to build the **human-facing command center** for AutoFlow AI: a polished, premium, engineering-oriented interface where a user can understand tasks, workflows, agents, approvals, executions, knowledge, files and artifacts.

This phase uses realistic local mock data and local frontend state only.

No backend API, database, model provider, AI execution, browser automation, desktop automation, authentication service, or real workflow engine is required.

The desktop should represent the architecture already established for AutoFlow:

```text
Desktop = Human-facing command center
Backend = future control plane
AI/ML = future intelligence plane
Execution = future execution plane
```

Only the Desktop is being built now.

---

# 2. Product Experience

AutoFlow should feel like an **engineering-grade digital worker command center**, not a conventional chatbot.

The primary interaction is:

```text
User Goal
   ↓
Task
   ↓
Task Graph
   ↓
Agents
   ↓
Execution
   ↓
Approval
   ↓
Artifacts
```

The interface should make this process understandable without exposing hidden model chain-of-thought.

The UI should answer:

1. What is AutoFlow doing?
2. Why is it doing it?
3. Which agent or system is involved?
4. What requires approval?
5. How do we know the result succeeded?

---

# 3. Design Principles

## 3.1 Strict Monochrome

The application must use only:

- black
- white
- neutral grayscale

Do not use:

- blue
- green
- red
- purple
- orange
- gradients
- colorful badges
- colorful illustrations

Status is communicated through icons, borders, typography, opacity and contrast.

Example:

```text
RUNNING       ●
COMPLETE      ✓
APPROVAL      !
FAILED        ×
PAUSED        —
```

---

## 3.2 Premium Technical Aesthetic

The visual language should feel like:

> premium developer platform + enterprise operations console

Prioritize:

- strong typography
- clear hierarchy
- thin borders
- restrained corner radius
- subtle panel contrast
- compact controls
- generous spacing
- dense but readable information
- technical iconography

Avoid:

- glassmorphism
- neon effects
- large gradients
- colorful AI avatars
- decorative blobs
- excessive shadows
- playful consumer-AI styling

---

## 3.3 Desktop First

Primary design target:

```text
1440 × 900
```

Secondary target:

```text
1280 × 800
```

Mobile is not a priority for this phase.

---

## 3.4 Not a ChatGPT Clone

The primary interface must not be a large chat window with a sidebar.

Natural language is the entry point, but the **task, graph, execution and evidence are first-class objects**.

---

# 4. Technology Requirements

Use:

```text
Next.js
React
TypeScript
shadcn/ui
Tailwind CSS
```

Use the Next.js App Router.

Frontend components should be organized so mock state can later be replaced with backend APIs without redesigning the UI.

---

# 5. Application Shell

Use a stable three-region desktop shell:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Top Bar                                                             │
├───────────────┬──────────────────────────────────┬──────────────────┤
│               │                                  │                  │
│   Sidebar     │         Main Workspace           │ Context /        │
│               │                                  │ Activity Panel    │
│               │                                  │                  │
└───────────────┴──────────────────────────────────┴──────────────────┘
```

The shell remains persistent while individual pages change.

---

# 6. Global Navigation

Left sidebar navigation:

```text
WORKSPACE

Tasks
Agents
Workflows
Knowledge
Files

Approvals
Executions

Settings
```

The sidebar should include:

- active route
- icon + label
- workspace selector
- collapse control
- user/profile area

Use shadcn/ui primitives and a consistent icon system.

---

# 7. Top Bar

Top bar should contain:

- current context/page
- workspace name
- global search
- activity/notification indicator
- user menu

Keep the bar quiet and functional.

It must not compete with the task workspace.

---

# 8. Workspace / Dashboard

The home screen is a command center and launch point.

Example:

```text
┌──────────────────────────────────────────────────────────────┐
│ What do you want AutoFlow to do?                            │
│                                                              │
│ Prepare this week's operations report from approved data... │
│                                                              │
│ + Attach file    Workspace: Operations        [ Run Task ]  │
└──────────────────────────────────────────────────────────────┘

Recent Tasks
───────────────────────────────────────────────────────────────
Operations report          RUNNING
Invoice reconciliation    COMPLETE
Research summary          AWAITING APPROVAL

Execution Overview
───────────────────────────────────────────────────────────────
Running     02
Approval    01
Completed   14
Failed      01
```

Use mock data.

---

# 9. Task Composer

The task composer is the primary interaction.

Required UI:

```text
┌──────────────────────────────────────────────────────────────┐
│ What do you want AutoFlow to do?                            │
│                                                              │
│ Prepare this week's sales report from approved data,        │
│ attach it to an email for finance, and ask me before        │
│ sending.                                                     │
│                                                              │
│ + Attach file      Workspace: Operations       Run →        │
└──────────────────────────────────────────────────────────────┘
```

Support visually:

- multiline goal input
- file attachment
- workspace selector
- optional constraints
- Run Task button
- keyboard shortcut
- recent tasks/prompts

The Run action only changes mock UI state.

---

# 10. Task Detail Page

This is the core application page.

Suggested layout:

```text
┌───────────────────────────────────────────────────────────────────┐
│ Weekly Sales Report                                   RUNNING    │
│ task_01HX...                                                     │
├─────────────────────────────────────┬─────────────────────────────┤
│ TASK GRAPH                          │ LIVE EXECUTION              │
│                                     │                             │
│ 01 Retrieve data       ✓            │ Planner          ✓          │
│ 02 Analyze data        ✓            │ Research         ✓          │
│ 03 Create report       ●            │ Spreadsheet      ●          │
│ 04 Verify              ○            │ Verification     ○          │
│ 05 Draft email         ○            │ Communication    ○          │
│ 06 Approval            ○            │                             │
│ 07 Send                ○            │ Current action              │
│                                     │ Creating report.xlsx        │
│                                     │                             │
├─────────────────────────────────────┴─────────────────────────────┤
│ Evidence / Artifacts / Timeline                                   │
└───────────────────────────────────────────────────────────────────┘
```

Show:

- task goal
- execution ID
- state
- task graph
- dependencies
- agents
- plan version
- attached inputs
- approval checkpoints
- live progress
- artifacts
- verification
- recovery attempts
- final outcome

---

# 11. Task Graph

The task graph represents the structured workflow.

Example:

```text
[01] Retrieve Data
        │
        ▼
[02] Analyze Sales
        │
        ├───────────────┐
        ▼               ▼
[03] Create Report   [04] Validate Data
        │               │
        └───────┬───────┘
                ▼
        [05] Prepare Email
                │
                ▼
        [06] Approval
                │
                ▼
             [07] Send
```

Each node should show:

- step number
- objective
- agent
- status
- dependency state
- verification state

Use monochrome node treatments.

Selecting a node opens a details drawer.

---

# 12. Agent Activity

The live execution panel should communicate operational status without exposing private reasoning.

Example:

```text
Planner Agent                    ✓
Created execution plan

Research Agent                   ✓
Retrieved 3 sources

Spreadsheet Agent                ●
Generating report.xlsx

Verification Agent               ○
Waiting for report

Communication Agent              ○
Waiting
```

Agent details can show:

- responsibility
- current state
- current step
- tools used
- outputs
- verification
- elapsed time

Do not show raw chain-of-thought.

---

# 13. Execution Timeline

Provide a chronological event stream.

Example:

```text
17:41:04   Task created
17:41:05   Plan generated
17:41:06   Plan validated
17:41:09   Data retrieval started
17:41:13   Data retrieval completed
17:41:18   Report generation started
17:41:24   Report generated
17:41:26   Verification passed
17:41:27   Email draft prepared
17:41:27   Approval required
```

Use compact typography and clear separators.

---

# 14. Approval Experience

Approval is a prominent workflow surface.

Example:

```text
┌─────────────────────────────────────────────┐
│ Approval required                           │
│                                             │
│ Send email to Finance                       │
│                                             │
│ Recipient                                   │
│ finance@example.com                         │
│                                             │
│ Attachment                                  │
│ report.xlsx                                 │
│                                             │
│ Evidence                                    │
│ ✓ Report verified                           │
│ ✓ Required fields present                   │
│                                             │
│ [ Reject ]                    [ Approve ]   │
└─────────────────────────────────────────────┘
```

Display:

- action
- recipient/target
- risk
- evidence
- affected artifact
- plan/action information
- expiry/status

Use no semantic colors.

Mock Approve/Reject interactions should update local UI state.

---

# 15. Failure and Recovery UI

Failures must communicate facts, not dramatize them.

Example:

```text
Step 4 needs recovery

The application state changed.

AutoFlow is re-checking the target.

Attempt 1 / 3

[ View Details ]   [ Pause ]   [ Cancel ]
```

Failed recovery:

```text
Could not safely complete this step.

No external action was performed.

Reason:
The target could not be verified.

[ Retry ] [ Resume Manually ] [ End Task ]
```

Never visually imply success when the task is incomplete.

---

# 16. Artifacts

Artifacts are first-class UI objects.

Categories:

```text
Documents
Spreadsheets
Presentations
Images
Code
Reports
Logs
```

Artifact cards show:

- filename
- type
- size
- creation time
- task association
- verification state
- available actions

Example:

```text
┌────────────────────────────────────────────┐
│ report.xlsx                                │
│ Spreadsheet · 248 KB                       │
│                                            │
│ Verified                                   │
│ Weekly Operations Report                   │
│                                            │
│ [ Open ] [ Download ] [ Details ]          │
└────────────────────────────────────────────┘
```

---

# 17. Files

The Files page should resemble a clean technical file browser.

Provide UI for:

- folders
- files
- search
- sorting
- filters
- upload
- file preview
- metadata

All content can be mocked.

---

# 18. Agents Page

Show specialist agents as reusable capability profiles.

Initial visual set:

```text
Planner
Plans multi-step work

Research
Finds and synthesizes evidence

Documents
Creates and validates documents

Spreadsheet
Analyzes and creates spreadsheets

Presentation
Creates presentation artifacts

Coding
Writes and tests code

Data Analysis
Analyzes structured data

Communication
Creates communications

Computer Automation
Operates supported applications

Verification
Validates outputs and outcomes
```

Each card shows:

- name
- purpose
- capabilities
- status
- tools
- recent activity

---

# 19. Workflows Page

Represent reusable verified workflow patterns.

Example:

```text
Weekly Operations Report
Last verified: Today
Runs: 18
Success rate: 94%

Invoice Processing
Last verified: Yesterday
Runs: 41
Success rate: 97%

Repository QA
Last verified: 3 days ago
Runs: 12
Success rate: 91%
```

The UI should make workflows feel like reusable operational knowledge, not chat history.

---

# 20. Knowledge Page

Represent organizational knowledge and provenance.

Provide UI for:

- search
- source list
- categories
- workspace scope
- access scope
- version
- provenance
- update time

This phase only visualizes the concept.

---

# 21. Executions Page

The Executions page is an operational history table.

Columns:

```text
Execution
Task
Status
Agent
Started
Duration
Verification
```

Example:

```text
exec_1002
Weekly report
RUNNING
Spreadsheet
17:41
02m 12s
—

exec_1001
Invoice report
COMPLETE
Data Analysis
16:23
04m 08s
PASSED
```

Provide:

- search
- status filters
- sort
- execution detail navigation

---

# 22. Approvals Page

Central approval queue.

Example:

```text
Pending approvals

01  Send finance report
    External communication
    Requested 2 minutes ago

02  Publish operations update
    Publication
    Requested 11 minutes ago
```

Selecting an approval opens a detailed review surface.

---

# 23. Settings Page

Visual/mock settings only.

Sections:

```text
General
Appearance
Workspace
Model Providers
Automation
Notifications
Security
About
```

No actual settings need to be persisted.

---

# 24. Global Search

Use a command-palette style interface.

Shortcut:

```text
Ctrl + K
```

Search across:

```text
Tasks
Workflows
Agents
Files
Artifacts
Knowledge
Executions
```

Use shadcn/ui command components.

---

# 25. Reusable Components

Create reusable components for:

```text
AppShell
Sidebar
TopBar
WorkspaceSelector

TaskComposer
TaskCard
TaskGraph
TaskNode

AgentCard
AgentStatus

ExecutionTimeline
ExecutionEvent

ApprovalCard
ApprovalModal

ArtifactCard
FileBrowser

WorkflowCard
KnowledgeSourceCard

StatusBadge
EmptyState
LoadingState
ErrorState

DetailDrawer
CommandPalette
```

Prefer composition using shadcn/ui primitives.

---

# 26. Status System

Use a strictly monochrome state system:

```text
QUEUED             ○
PLANNING           ◐
VALIDATING         ◌
AWAITING_APPROVAL  !
RUNNING            ●
VERIFYING          ◉
COMPLETE           ✓
FAILED             ×
CANCELLED         —
BLOCKED            ⊘
```

Use:

- icons
- border treatment
- typography
- opacity
- contrast

instead of color.

---

# 27. Typography

Use a modern technical hierarchy.

Required levels:

```text
Page title
Section heading
Card heading
Body
Metadata
Timestamp
Monospace identifier
```

Technical IDs should use monospace:

```text
task_01HX...
exec_01HX...
agent_run_...
tool_call_...
```

---

# 28. Visual Rules

Favor:

```text
white canvas
black typography
neutral-gray secondary text
thin borders
subtle panel contrast
restrained radius
strong grid alignment
clear spacing
```

Avoid:

```text
glassmorphism
neon
heavy gradients
large drop shadows
colorful illustrations
consumer-style AI imagery
```

---

# 29. Mock Data

Create local mock data with enough depth to make the application look real.

Minimum:

```text
3+ workspaces
10+ tasks
10 agents
5+ workflows
10+ executions
5+ approvals
10+ artifacts
10+ knowledge sources
```

Data should support the complete navigation and detail views.

---

# 30. Frontend State

Use local state only.

Required examples:

```text
selected workspace
selected task
selected execution
task status
agent status
approval state
active navigation item
sidebar state
command palette state
detail drawer state
selected graph node
```

Keep mock data and state isolated behind simple frontend interfaces so they can later be replaced with API-backed data.

---

# 31. Routes

Initial route structure:

```text
/
 /tasks
 /tasks/[id]

 /agents
 /agents/[id]

 /workflows
 /workflows/[id]

 /knowledge
 /knowledge/[id]

 /files
 /files/[id]

 /approvals

 /executions
 /executions/[id]

 /settings
```

A mock login screen may be included for visual completeness, but there is no real authentication implementation.

---

# 32. Empty States

Every major section must have a deliberate empty state.

Examples:

```text
No active tasks

Start with a goal and AutoFlow will build the workflow.
```

```text
No pending approvals

Everything requiring your decision will appear here.
```

```text
No workflows yet

Verified workflows will appear here after successful executions.
```

Keep them minimal and monochrome.

---

# 33. Loading States

Use shadcn-compatible skeletons and subtle transitions.

Avoid:

- colorful loaders
- excessive spinners
- distracting animation

---

# 34. Interactions

Required working frontend interactions:

```text
Navigation
Task creation with mock data
Task selection
Task graph node selection
Agent selection
Approval open/close
Mock approve/reject
Execution filtering
Search
Command palette
Artifact preview
Sidebar collapse
Detail drawer
```

All interactions may remain entirely local.

---

# 35. Accessibility

Required:

- keyboard navigation
- visible focus states
- semantic buttons
- accessible labels
- accessible icon-only controls
- sufficient monochrome contrast
- status labels that do not rely on color

---

# 36. Animation

Use only subtle functional motion.

Allowed:

```text
sidebar transition
drawer transition
modal transition
task-node status transition
skeleton loading
command palette transition
```

Avoid decorative continuous motion.

---

# 37. Frontend Structure

Suggested structure:

```text
app/
├── page.tsx
├── tasks/
├── agents/
├── workflows/
├── knowledge/
├── files/
├── approvals/
├── executions/
└── settings/

components/
├── layout/
├── tasks/
├── agents/
├── workflows/
├── knowledge/
├── files/
├── approvals/
├── executions/
└── shared/

components/ui/
# shadcn/ui components

lib/
├── mock-data.ts
├── constants.ts
├── types.ts
└── utils.ts

public/
└── assets/
```

---

# 38. Explicitly Out of Scope

Do NOT implement:

```text
Backend APIs
Database
Authentication backend
Real AI calls
LLM providers
Agent execution
Model routing
RAG/vector database
Real browser automation
Real desktop automation
Real email sending
Real workflow persistence
Real approval enforcement
Real security enforcement
Real execution workers
Production deployment
```

Only the frontend experience is being built.

---

# 39. Frontend Acceptance Criteria

## Visual

```text
✓ Entire interface is monochrome
✓ No semantic colors
✓ Desktop-first layout
✓ Consistent spacing and typography
✓ Premium technical aesthetic
✓ Consistent shadcn component language
```

## Product UX

```text
✓ User can enter a task
✓ User can inspect task details
✓ User can view task graph
✓ User can view agents
✓ User can view execution progress
✓ User can review approvals
✓ User can inspect artifacts
✓ User can browse workflows
✓ User can browse knowledge
✓ User can browse executions
```

## Interaction

```text
✓ Navigation works
✓ Mock task creation works
✓ Mock execution state works
✓ Approval interaction works
✓ Search works
✓ Command palette works
✓ Drawers/modals work
✓ Filters work
```

## Architecture

```text
✓ Next.js
✓ React
✓ TypeScript
✓ shadcn/ui
✓ Tailwind CSS
✓ Local mock data
✓ Local frontend state
✓ No backend dependency
✓ No AI-provider dependency
✓ No execution-engine dependency
```

---

# 40. Final Frontend Definition

For this phase:

> **Build the visual command center of AutoFlow AI using Next.js, React, TypeScript, shadcn/ui and Tailwind CSS, with a strict black-and-white design language.**

The frontend should let a user:

```text
enter a goal
    ↓
inspect the task
    ↓
see the task graph
    ↓
see specialist agents
    ↓
observe execution
    ↓
review approval
    ↓
inspect artifacts
    ↓
inspect workflow history
```

The entire experience may be powered by mocked/local state.

The UI should look and behave like the command center of the eventual AutoFlow system while remaining completely independent from backend and AI implementation.

