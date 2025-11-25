# Architecture Diagram (Mermaid)

This repo uses a Simple Advanced Coordinator built on Google ADK to fan out specialist compliance agents, loop in humans for low-confidence items, and emit a structured compliance report. The diagram below captures the runtime topology, data flow, tools, and external dependencies.

```mermaid
flowchart TD
    subgraph Entrypoints
        U1["CLI Demo (demo.py)"]
        U2["FastAPI UI (app.py)"]
    end

    subgraph Coordinator["SimpleAdvancedCoordinator\n(src/coordinator_simple.py)"]
        DC["DocumentLoader FunctionTool\nDocumentProcessor.load_document"]
        NB["Nano Banana Probe FunctionTool\nheuristic scan + context tags"]
        PAR["ParallelAgent: SpecialistParallel"]
        LOOP["LoopAgent: HumanReviewLoop"]
        SEQ["SequentialAgent: CoordinatorPipeline"]
        BUILD["_build_final_report\naudit log + summary + topology"]
        HUMANREVIEW["_identify_human_review_needs"]
    end

    subgraph Specialists["Specialist Agents"]
        REQ["RequirementsAgent\n(Gemini + Google Search Tool)"]
        RISK["RiskAgent\n(Gemini + Google Search Tool)"]
        TEST["TestAgent\n(Gemini + Nano Probe)"]
        GUIDE["GuidelineAgent\n(Gemini + Google Search Tool)"]
    end

    subgraph External
        GEM["Google Gemini API\n(model from config/env)"]
        GSEARCH["Google Search Tool"]
    end

    subgraph Outputs
        SUM["SummarizerAgent\nexecutive synthesis"]
        REPORT["Compliance Report JSON\nstatus, findings, recommendations, audit trail"]
        FILE["data/compliance_report_parallel.json (demo)"]
    end

    U1 -->|document path| SEQ
    U2 -->|document path| SEQ

    SEQ --> DC
    DC -->|text content| NB
    NB -->|augmented context| PAR
    PAR --> REQ
    PAR --> RISK
    PAR --> TEST
    PAR --> GUIDE

    REQ -->|analysis JSON| HUMANREVIEW
    RISK -->|analysis JSON| HUMANREVIEW
    TEST -->|analysis JSON| HUMANREVIEW
    GUIDE -->|analysis JSON| HUMANREVIEW

    HUMANREVIEW -->|low confidence / failures| LOOP
    LOOP -->|human decisions| HUMANREVIEW

    HUMANREVIEW --> SUM
    SUM --> BUILD
    BUILD --> REPORT
    REPORT --> FILE

    REQ -.->|LLM calls| GEM
    RISK -.->|LLM calls| GEM
    TEST -.->|LLM calls| GEM
    GUIDE -.->|LLM calls| GEM
    REQ -.->|search| GSEARCH
    RISK -.->|search| GSEARCH
    GUIDE -.->|search| GSEARCH
```

Key flow:
- User triggers via CLI or FastAPI with a document path; `DocumentProcessor` loads content and applies a lightweight nano probe for quick heuristics/context tags.
- `ParallelAgent` fans out to four Gemini-backed specialists (requirements, risk, test, guideline). Tools: Google Search where allowed; Nano Probe for test agent; Google Gemini for generation.
- Results feed `_identify_human_review_needs` to flag agent failures or low-confidence findings; `LoopAgent` waits for human decisions and rehydrates state when feedback arrives.
- `SummarizerAgent` synthesizes specialist output plus human decisions into an executive summary; `_build_final_report` adds audit trail, recommendations, and ADK topology before emitting JSON (written by demo to `data/compliance_report_parallel.json`).

State management:
- `session_state` tracks document content/path, additional context, specialist outputs, human review queue, summary, audit log, and ADK topology for transparency/telemetry.

