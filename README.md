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

- [x] **🧠 Phase 4: Reasoning, State, & Logic Hosting**
  - [x] **State Tracking (Scene Memory)**: Cross-take chronological continuity memory, sequential drift tracking, compact verdict synthesis without context bloat, and interactive take timeline.
  - [x] **Function Calling & Tool Use (Autonomous Agent Copilot)**: Native Automatic Function Calling (AFC) with `gemini-3.8-flash`, autonomous multi-step execution across 8 production tools, and interactive Tool Execution Traces.
  - [x] **Actionable Fixes (Department Action Checklist)**: Autonomous synthesis of department-specific fix checklists (`generate_department_checklist`) for Makeup, Wardrobe, Hair, and Props before next take.
  - [x] **Hands-Free Voice Mode**: On-set hands-free voice commanding via browser-native SpeechRecognition & SpeechSynthesis with auto-listen continuity.
  - [x] **Studio MCP Server**: Model Context Protocol (MCP) server exposing 8 tools via SSE (`/mcp/sse`) and stdio for NLE suites and external assistants.
  - [x] **Agent Engine & Managed Hosting (Google Cloud ADK / Vertex AI)**: Packaged according to Google Cloud Agent Development Kit (ADK) and Vertex AI Reasoning Engine standards for serverless deployment (`agent_engine/`, `Dockerfile.agent_engine`, `deploy_vertex.py`).

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

## MCP Integration (Studio MCP Server)

Flawless Take exposes all 8 continuity tools via the **Model Context Protocol (MCP)** — the open standard for connecting AI tools to data sources and services. Studio editing systems, Claude Desktop, Cursor, and custom agents can invoke on-set continuity data with zero custom integration code.

### SSE Endpoint

```
http://localhost:8000/mcp/sse
```

Verify the server is live:
```bash
curl http://localhost:8000/api/mcp-info
```

### Claude Desktop Integration

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS or `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "flawless-take": {
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp/sse
```

### Exposed Tools

| Tool | Description |
|------|-------------|
| `get_scene_continuity_state` | Drift status, baseline take, take history |
| `query_take_records` | SQLite database search by scene/character |
| `get_take_full_report` | Full Gemini analysis for a record ID |
| `check_script_continuity` | Shooting script requirements for a scene |
| `compare_recorded_takes` | Take-vs-take differential (match score) |
| `emit_crew_alert` | Kafka + SSE real-time crew alert |
| `export_continuity_pdf` | Hollywood Continuity Log PDF |
| `generate_department_checklist` | Structured fix checklist by department |

### stdio (Local Claude Desktop without HTTP)

```bash
cd backend
python mcp_server.py
```

---

## Google Cloud Agent Engine & ADK Packaging

Flawless Take's continuity supervisor agent is packaged following the official **Google Cloud Agent Development Kit (ADK)** and **Vertex AI Reasoning Engine** architecture for serverless hosting.

### Package Structure

```
backend/agent_engine/
├── __init__.py           # Exports ContinuitySupervisorAgent
├── agent.py              # ADK & Vertex AI Reasoning Engine compliant Agent (set_up, query, async_query)
├── manifest.json         # Standard ADK Agent Manifest (8 tools, schema, model config)
├── deploy_vertex.py      # Vertex AI Reasoning Engine automated deployment script
├── serverless_app.py     # Cloud Run / Serverless ASGI runtime (/health, /spec, /query)
└── test_local.py         # Offline ADK agent test harness
Dockerfile.agent_engine   # Production serverless container for Cloud Run & Vertex AI
```

### 1. Local ADK Verification

Test that the ADK agent manifest, tool bindings, and Reasoning Engine contract pass locally:

```bash
python backend/agent_engine/test_local.py
```

Or inspect the ADK manifest via the running backend API:

```bash
curl http://localhost:8000/api/agent-engine/info
```

### 2. Deploy to Google Cloud Vertex AI Agent Engine

Deploy directly into Vertex AI Reasoning Engine managed serverless runtime:

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Deploy using the deployment script
python backend/agent_engine/deploy_vertex.py \
  --project YOUR_GCP_PROJECT_ID \
  --location us-central1 \
  --staging-bucket gs://your-staging-bucket \
  --display-name "flawless-take-continuity-supervisor"
```

Once deployed, remote NLEs and cloud services can query the agent:

```python
from vertexai.preview import reasoning_engines

agent = reasoning_engines.ReasoningEngine("projects/.../locations/.../reasoningEngines/...")
result = agent.query(
    prompt="Check for continuity drift in Scene 14A",
    scene="Scene 14A"
)
print(result["response"])
```

### 3. Serverless Container on Google Cloud Run

Build and deploy the self-contained ADK serverless container to Google Cloud Run:

```bash
# Build container image
docker build -f Dockerfile.agent_engine -t gcr.io/YOUR_PROJECT/flawless-take-agent-engine:latest .

# Deploy to Cloud Run
gcloud run deploy flawless-take-agent-engine \
  --image gcr.io/YOUR_PROJECT/flawless-take-agent-engine:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_gemini_api_key
```

The deployed Cloud Run service provides:
- `GET /health` — Liveness and readiness probe.
- `GET /spec` — Returns the official Google Cloud ADK agent manifest.
- `POST /query` — Processes agent queries with multi-step tool calling.

---

## License

This project is licensed under the [MIT License](LICENSE).
