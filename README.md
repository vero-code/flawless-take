# Flawless Take

AI-powered on-set continuity supervisor and goof detector for film and television production. Built for the **Agentic Cinema: The Blockbuster Hackathon** (IBM Partner Track).

---

## Overview

Maintaining visual continuity across takes, shooting days, and reverse-shot coverage is a major operational challenge on film sets. Minor oversights—missing SFX wounds, shifted collars, altered hairstyles, or inconsistent props—lead to expensive reshoots or visible continuity goofs.

**Flawless Take** provides an on-set tablet interface for script supervisors, makeup artists, and costume departments:
- Verifies individual takes against scene and character descriptions.
- Performs differential visual comparisons between an approved reference take and a newly shot take.
- Dispatches live continuity alerts via Confluent Kafka and SSE.
- Generates industry-standard **Continuity Log PDFs** for daily production wrap.

---

## Architecture & Tech Stack

```
[ PDF Shooting Script ] ──> Gemini 3.8 Flash ──> Structured Continuity Context
                                                         │
[ Camera Take Photos  ] ──> Gemini 3.8 Flash ──> Continuity Report / Diff
                                                         │
                                               FastAPI Backend
                                            ├── SQLite (History & Metadata)
                                            ├── Local / GCS Storage (Previews)
                                            ├── Confluent Kafka (Event Stream)
                                            └── ReportLab (PDF Log Export)
                                                         │
                                                React 19 Frontend
                                            ├── Single / Compare Mode
                                            ├── Live SSE Alerts
                                            └── Daily Continuity Gallery
```

- **Google Cloud & Gemini**: Uses `gemini-3.8-flash` via the official `google-genai` SDK for multimodal script parsing, single-take continuity evaluation, and dual-image differential analysis.
- **IBM Bob**: Used as part of the core development process for application scaffolding, API schema design, and initial architecture.
- **Confluent Kafka**: Event streaming backbone. The backend publishes `continuity_check` and `takes_comparison` events to the `flawless-take-events` topic for real-time crew notification.
- **Backend**: FastAPI (Python 3.12+), `aiosqlite` for asynchronous history persistence, `reportlab` for PDF generation.
- **Frontend**: React 19, TypeScript, Vite.

---

## Key Features

1. **Single Take Inspection**: Analyzes hair, makeup, wardrobe, and props from a single photo. Assigns a continuity risk rating (`LOW`, `MEDIUM`, `HIGH`).
2. **Dual-Take Differential Comparison**: Compares an approved reference frame against a current take. Isolates only visual discrepancies and outputs an overall match score (`GOOD`, `FAIR`, `POOR`).
3. **Script Grounding**: Ingests PDF shooting scripts and extracts character appearance rules and scene-specific continuity notes to ground visual checks.
4. **Live Alert Stream**: Emits real-time SSE alerts to notify connected crew members of high-risk continuity mismatches immediately after a take.
5. **Continuity History & Gallery**: Searchable, filterable local archive of all checks and comparisons with side-by-side previews.
6. **Official PDF Export**: Generates printable, Hollywood-standard **Script Supervisor Continuity Logs** with embedded photos, metadata, findings, and sign-off lines.

---

## Hackathon Roadmap

Aligned with the **Agentic Cinema Hackathon Guide**:

- [x] **🛠️ Phase 1: Core Frameworks & Environment**
  - Scaffolding of FastAPI backend and React 19 / TypeScript tablet interface.
  - Integration with the official `google-genai` SDK using `gemini-3.8-flash`.
  - Secure environment configuration and local runner tooling (`start.bat`).

- [x] **🎬 Phase 2: Action Mechanisms & Data Connectivity (GenMedia Focus)**
  - **Script Grounding**: Multimodal PDF shooting script parsing for scene and character continuity constraints.
  - **Single Take Visual Analysis**: Inspection of hair, makeup, wardrobe, and props from camera captures.
  - **Dual-Take Differential Diff**: Comparative image analysis identifying exact visual deviations between takes.

- [x] **🤝 Phase 3: Partner Integration & Infrastructure**
  - **IBM Bob**: Application architecture, data models, and initial scaffolding built with IBM Bob.
  - **Confluent Kafka**: Real-time event pipeline emitting continuity checks to the `flawless-take-events` topic.
  - **Live Alert Stream**: Real-time Server-Sent Events (SSE) broadcasting instant risk warnings to production crew.
  - **Daily Continuity Gallery**: Asynchronous SQLite (`aiosqlite`) persistence and searchable history for on-set review.
  - **Continuity Log PDF Export**: ReportLab generator outputting official Hollywood-standard continuity logs with embedded photos.

- [ ] **🧠 Phase 4: Reasoning, State, & Logic Hosting**
  - [x] **State Tracking (Scene Memory)**: Cross-take chronological continuity memory, sequential drift tracking, compact verdict synthesis without context bloat, and interactive take timeline.
  - [x] **Function Calling & Tool Use (Autonomous Agent Copilot)**: Native Automatic Function Calling (AFC) with `gemini-3.8-flash`, autonomous multi-step execution across 7 production tools (SQLite query, script checking, take diff comparison, Kafka/SSE radio alerts, PDF generation), and interactive Tool Execution Traces.
  - [ ] **Agent Engine & Managed Hosting**: Managed hosting and deployment on Vertex AI Agent Engine.

- [ ] **🚀 Phase 5: Deployment & Safety** 


---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Google Gemini API Key
- (Optional) Confluent Cloud Kafka cluster credentials

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/your-username/flawless-take.git
cd flawless-take

# Set up Python virtual environment
python -m venv backend/.venv

# Activate virtual environment
# Windows (cmd):
backend\.venv\Scripts\activate.bat
# Windows (bash / Git Bash):
source backend/.venv/Scripts/activate
# macOS / Linux:
source backend/.venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env and add your GEMINI_API_KEY (and optional CONFLUENT credentials)
```

### 2. Frontend Setup

```bash
# Install frontend dependencies
npm install
```

### 3. Run Locally

**Option A: Quick launch (Windows)**
Double-click `start.bat` or run:
```cmd
start.bat
```

**Option B: Separate terminals**

Terminal 1 (Backend):
```bash
# Ensure venv is active
uvicorn backend.main:app --reload --port 8000
```

Terminal 2 (Frontend):
```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## License

This project is licensed under the [MIT License](LICENSE).
