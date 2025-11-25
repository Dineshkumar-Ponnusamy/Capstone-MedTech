## Multi-Agent Compliance Reviewer (Google ADK)

Track: **Agents for Good — Healthcare/MedTech compliance**

A multi-agent system for rapid regulatory document review in medical devices. Uses Google ADK to fan out specialist agents (requirements, risk, test, guidelines), pipeline them through a summarizer, and loop in humans for low-confidence findings. Includes built-in tools (Google Search) and custom FunctionTools.

### Key Features
- **Global compliance brain:** Prompts are grounded in ISO 13485/14971, IEC 62304/60601/62366, EU MDR/IVDR, FDA 21 CFR Part 820/11, NIST, and DoD STIG so findings map to real-world regulators.
- **Full document coverage:** Handles PDF, DOCX, TXT/MD, CSV, and legacy DOC (via textract) with a hard 10MB guardrail to keep UX safe and predictable.
- **Resilient orchestration:** Google ADK Parallel/Sequential/Loop patterns plus persisted job state (`data/jobs_state.json`) to survive restarts while keeping the audit trail intact.
- **Human-in-the-loop ready:** Flags low confidence/agent failures for human decisions and re-summarizes with those decisions applied.
- **Demo-ready UX:** CLI demo, FastAPI UI for a quick visual walkthrough, structured JSON reports for scoring.

### Pitch (Problem / Solution / Value)
- **Problem:** Regulatory reviews for medical devices are slow, error-prone, and require coordinated expertise across requirements, risk, testing, and standards.
- **Solution:** A Parallel + Sequential + Loop ADK workflow that ingests a document, runs specialist Gemini agents concurrently, aggregates findings, and routes low-confidence items for human approval.
- **Value:** Faster compliance checks, clearer action items, audit trail for regulators, and human-in-the-loop where judgment is needed.

### ADK Features Demonstrated
- **Multi-agent orchestration:** Parallel specialist agents; Sequential summarization; Loop for human review.
- **Tools:** Google Search built-in tool + custom FunctionTools (nano probe, document loader).
- **Sessions & state:** Coordinator session state captures specialist outputs, human reviews, summaries, and audit log.
- **Observability:** Structured logging; audit trail in final report.

### What’s Included
- `src/coordinator_simple.py` — Coordinator orchestrating specialist agents, summarizer, human review loop, ADK tools.
- `src/agents/*` — Gemini-backed specialist agents and summarizer with global regulatory context in prompts.
- `demo.py` — CLI demo: runs parallel analysis on a sample doc, produces JSON report, simulates human approvals.
- `app.py` — Optional FastAPI UI wrapper with persisted job tracking (`data/jobs_state.json`) and hourly cleanup.
- `config/config.yaml` — Defaults (model/temperature, chunk sizes). **No keys stored here.**
- `data/sample_medical_device_requirements.txt` — Demo input.
- `tests/test_document_processor.py` — Parser tests including 10MB guardrail and legacy DOC via textract.
- `tests/test_job_store.py` — Persistence and cleanup coverage for the job store.

### Setup
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Configure credentials (preferred via environment):
```bash
export GEMINI_API_KEY="your-key"          # required
export GEMINI_MODEL="gemini-2.0-flash"    # optional override (matches config default)
```
You can also copy `.env.example` to `.env` and fill values, then:
```bash
export $(grep -v '^#' .env | xargs)
```
Local runs auto-load `.env` via python-dotenv (app and demo); production should use real environment variables instead.

### Run the CLI Demo
```bash
python demo.py
```
This will:
- Load `data/sample_medical_device_requirements.txt`
- Run 4 specialist agents in parallel
- Flag low-confidence/failed agents for human review
- Produce `data/compliance_report_parallel.json`
- Simulate human approvals

### Run the FastAPI UI (optional)
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
Then open http://localhost:8000 (lightweight HTML front-end).

### Tests
```bash
python -m pytest tests -v
```

### Dependencies of note
- **google-adk** for orchestration primitives.
- **textract** for legacy `.doc` support (may require system packages depending on OS).

### Notes on Models
- Default model comes from `config/config.yaml` (gemini-2.0-flash). Override with `GEMINI_MODEL`.
- If you see 404s, list available models for your key:
```bash
python - <<'PY'
import google.generativeai as genai, os
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
for m in genai.list_models():
    print(m.name, m.supported_generation_methods)
PY
```
Pick one that supports `generateContent` (e.g., `gemini-1.5-flash-002`, `gemini-2.0-flash` if available).
