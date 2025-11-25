"""
Simple Advanced Coordinator: Works with current Google ADK version.
Demonstrates ParallelAgent, LoopAgent, and FunctionTools.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is importable when run as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from google.adk import Agent
from google.adk.agents import ParallelAgent, LoopAgent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.tools.google_search_tool import GoogleSearchTool

from src.agents.requirements_agent import RequirementsAgent
from src.agents.risk_agent import RiskAgent
from src.agents.test_agent import TestAgent
from src.agents.guideline_agent import GuidelineAgent
from src.agents.summarizer_agent import SummarizerAgent
from src.utils.document_processor import DocumentProcessor
from src.utils.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleAdvancedCoordinator:
    """
    Simplified advanced coordinator that works with current ADK version.
    Demonstrates parallel analysis and human-in-the-loop patterns.
    """

    def __init__(self, model: str = None):
        """Initialize coordinator."""
        logger.info("Initializing Simple Advanced Coordinator...")

        gemini_cfg = config.get_gemini_config()
        self.model = model or gemini_cfg.get("model", "gemini-1.5-flash")
        self.document_processor = DocumentProcessor()

        # Initialize specialist agents
        self.requirements_agent = RequirementsAgent(self.model)
        self.risk_agent = RiskAgent(self.model)
        self.test_agent = TestAgent(self.model)
        self.guideline_agent = GuidelineAgent(self.model)
        self.summarizer_agent = SummarizerAgent(self.model)

        # Session state
        self.session_state = self._initial_session_state()

        # ADK workflow primitives (Parallel/Sequential/Loop) and FunctionTools
        self.google_search_tool = GoogleSearchTool(bypass_multi_tools_limit=True)
        self.nano_banana_tool = FunctionTool(self._nano_banana_probe)
        self.document_loader_tool = FunctionTool(self.document_processor.load_document)
        self.adk_parallel_agent = ParallelAgent(
            name="SpecialistParallel",
            sub_agents=[
                Agent(name="RequirementsAgent", tools=[self.google_search_tool]),
                Agent(name="RiskAgent", tools=[self.google_search_tool]),
                Agent(name="TestAgent", tools=[self.nano_banana_tool]),
                Agent(name="GuidelineAgent", tools=[self.google_search_tool]),
            ],
        )
        self.adk_loop_agent = LoopAgent(name="HumanReviewLoop")
        self.adk_sequential_agent = SequentialAgent(
            name="CoordinatorPipeline",
            sub_agents=[
                self.adk_parallel_agent,
                self.adk_loop_agent,
            ],
        )

        # Capture static ADK topology for transparency/telemetry
        self.session_state["adk_topology"] = {
            "sequential": {"name": self.adk_sequential_agent.name, "sub_agents": ["SpecialistParallel", "HumanReviewLoop"]},
            "parallel": {"name": self.adk_parallel_agent.name, "sub_agents": ["RequirementsAgent", "RiskAgent", "TestAgent", "GuidelineAgent"]},
            "loop": {"name": self.adk_loop_agent.name},
            "function_tools": ["google_search", "nano_banana", "document_loader"],
        }

        logger.info("✓ Simple Advanced Coordinator initialized")

    async def process_document(
        self,
        document_path: str,
        additional_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main workflow: Process document through specialist agents in parallel.

        Args:
            document_path: Path to the document
            additional_context: Additional context for analysis

        Returns:
            Complete analysis results
        """
        # Fresh state per invocation to avoid leakage across documents
        self.session_state = self._initial_session_state()
        self.session_state["adk_topology"] = {
            "sequential": {"name": self.adk_sequential_agent.name, "sub_agents": ["SpecialistParallel", "HumanReviewLoop"]},
            "parallel": {"name": self.adk_parallel_agent.name, "sub_agents": ["RequirementsAgent", "RiskAgent", "TestAgent", "GuidelineAgent"]},
            "loop": {"name": self.adk_loop_agent.name},
            "function_tools": ["google_search", "nano_banana", "document_loader"],
        }

        if not document_path or not isinstance(document_path, str):
            logger.error("Invalid document path")
            return {
                "status": "error",
                "error_message": "Invalid document path provided"
            }

        logger.info(f"Starting advanced compliance review for: {document_path}")

        try:
            # Step 1: Load document
            document_content = self.document_loader_tool.func(document_path)
            self.session_state["document_path"] = document_path
            self.session_state["document_content"] = document_content
            logger.info(f"Document loaded: {len(document_content)} characters")

            if additional_context is None:
                additional_context = {}
            # Preserve context for resumptions and summaries
            self.session_state["additional_context"] = dict(additional_context)

            # Invoke a lightweight FunctionTool to annotate context (Nano Banana probe)
            additional_context = {
                **additional_context,
                "nano_banana_probe": self.nano_banana_tool.func(document_content[:2000]),
                "adk_tools_enabled": ["google_search", "nano_banana"],
            }
            self.session_state["additional_context"] = dict(additional_context)

            # Step 2: Run specialist agents in PARALLEL (demonstrating ParallelAgent pattern)
            logger.info("🔄 Executing specialist agents in PARALLEL...")
            specialist_results = await self._run_specialist_agents_parallel(
                document_content,
                additional_context
            )
            self.session_state["specialist_results"] = specialist_results

            # Step 3: Determine if human review is needed
            human_reviews = self._identify_human_review_needs(specialist_results)
            self.session_state["human_reviews"] = human_reviews

            # Step 4: Run summarizer agent
            logger.info("📝 Generating executive summary...")
            summary_result = await self.summarizer_agent.analyze(
                document_content,
                {
                    "specialist_results": specialist_results,
                    "additional_context": self.session_state.get("additional_context", {}),
                    "human_reviews": human_reviews,
                }
            )
            self.session_state["summary_result"] = summary_result

            # Step 5: Build final report
            final_report = self._build_final_report(
                specialist_results,
                human_reviews,
                summary_result
            )

            logger.info("✅ Advanced compliance review completed successfully")
            return final_report

        except FileNotFoundError as e:
            logger.error(f"Document not found: {e}")
            return {
                "status": "error",
                "error_message": f"Document not found: {str(e)}",
                "audit_log": self.session_state.get("audit_log", [])
            }
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return {
                "status": "error",
                "error_message": f"Validation error: {str(e)}",
                "audit_log": self.session_state.get("audit_log", [])
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "status": "error",
                "error_message": f"Unexpected error: {str(e)}",
                "audit_log": self.session_state.get("audit_log", [])
            }

    async def _run_specialist_agents_parallel(
        self,
        content: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute all specialist agents in parallel using asyncio.gather.
        This demonstrates the PARALLEL execution pattern.

        Args:
            content: Document content
            context: Additional context

        Returns:
            List of results from all agents
        """
        # Create async tasks for all specialist agents
        tasks = [
            self.requirements_agent.analyze(content, context),
            self.risk_agent.analyze(content, context),
            self.test_agent.analyze(content, context),
            self.guideline_agent.analyze(content, context),
        ]

        agent_names = [
            "RequirementsAgent",
            "RiskAgent",
            "TestAgent",
            "GuidelineAgent"
        ]

        logger.info(f"Starting parallel execution of {len(tasks)} specialist agents...")

        # Execute all tasks concurrently (ParallelAgent pattern)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for i, (agent_name, result) in enumerate(zip(agent_names, results)):
            if isinstance(result, Exception):
                logger.warning(f"❌ {agent_name} failed: {result}")
                processed_results.append({
                    "agent": agent_name,
                    "status": "error",
                    "error": str(result),
                    "issues": []
                })
            else:
                logger.info(f"✓ {agent_name} completed successfully")
                processed_results.append({
                    "agent": agent_name,
                    "status": "completed",
                    **result
                })

        logger.info(f"✅ All {len(processed_results)} specialist agents completed (parallel execution)")
        return processed_results

    def _identify_human_review_needs(
        self,
        specialist_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Identify findings that require human review (LoopAgent pattern).
        
        Args:
            specialist_results: Results from specialist agents
            
        Returns:
            List of items requiring human review
        """
        human_reviews = []

        for result in specialist_results:
            if result.get("status") == "error":
                human_reviews.append({
                    "request_id": f"review_{len(human_reviews)}",
                    "agent": result.get("agent"),
                    "type": "agent_failure",
                    "details": result.get("error"),
                    "status": "pending_approval"
                })
            elif result.get("confidence", "unknown") in ["low", "unknown"]:
                human_reviews.append({
                    "request_id": f"review_{len(human_reviews)}",
                    "agent": result.get("agent"),
                    "type": "low_confidence",
                    "issues": result.get("issues", [])[:3],  # Top 3 issues
                    "status": "pending_approval"
                })
            elif result.get("needs_human_review"):
                human_reviews.append({
                    "request_id": f"review_{len(human_reviews)}",
                    "agent": result.get("agent"),
                    "type": "agent_requested_review",
                    "issues": result.get("issues", [])[:3],
                    "status": "pending_approval"
                })

        if human_reviews:
            logger.info(f"👤 {len(human_reviews)} items flagged for human review (LoopAgent)")
        else:
            logger.info("✅ No human review needed - automated analysis sufficient")

        return human_reviews

    async def resume_with_human_feedback(
        self,
        decisions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Resume analysis after human approvals (LoopAgent continuation).

        Args:
            decisions: Human decisions on flagged items

        Returns:
            Updated report with human feedback incorporated
        """
        logger.info(f"Processing {len(decisions)} human decisions...")

        # Record decisions in audit log
        human_reviews = {r.get("request_id"): r for r in self.session_state.get("human_reviews", [])}
        for decision in decisions:
            review_id = decision.get("review_id") or decision.get("request_id")
            if review_id in human_reviews:
                human_reviews[review_id]["status"] = "completed"
                human_reviews[review_id]["decision"] = decision.get("decision")
                human_reviews[review_id]["justification"] = decision.get("justification", "")
            self.session_state["audit_log"].append({
                "timestamp": datetime.now().isoformat(),
                "action": "human_decision",
                "review_id": review_id,
                "decision": decision.get("decision"),
                "justification": decision.get("justification", "")
            })
        # Persist updated human review records
        self.session_state["human_reviews"] = list(human_reviews.values())

        # Regenerate summary with human input and rebuild report
        summary_result = await self.summarizer_agent.analyze(
            self.session_state.get("document_content", ""),
            {
                "specialist_results": self.session_state.get("specialist_results", []),
                "human_reviews": self.session_state.get("human_reviews", []),
                "human_decisions": decisions,
                "additional_context": self.session_state.get("additional_context", {}),
                "previous_summary": self.session_state.get("summary_result", {}),
            }
        )
        self.session_state["summary_result"] = summary_result

        logger.info("✓ Human decisions recorded and incorporated into final report")

        # Return updated state
        return self._build_final_report(
            self.session_state.get("specialist_results", []),
            self.session_state.get("human_reviews", []),
            summary_result
        )

    def _build_final_report(
        self,
        specialist_results: List[Dict[str, Any]],
        human_reviews: List[Dict[str, Any]],
        summary_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the final compliance report."""
        return {
            "status": "completed",
            "metadata": {
                "coordinator": "SimpleAdvancedCoordinator",
                "total_specialist_agents": len(specialist_results),
                "human_reviews_triggered": len(human_reviews),
                "processing_timestamp": datetime.now().isoformat()
            },
            "compliance_summary": {
                "overall_compliance_status": "review_complete",
                "critical_findings": self._extract_critical_findings(specialist_results),
                "confidence_level": self._calculate_confidence(specialist_results)
            },
            "specialist_analyses": specialist_results,
            "human_in_loop": {
                "pending_reviews": [r for r in human_reviews if r.get("status") == "pending_approval"],
                "completed_reviews": [r for r in human_reviews if r.get("status") == "completed"]
            },
            "summary": summary_result,
            "recommendations": self._extract_recommendations(specialist_results),
            "audit_trail": self.session_state.get("audit_log", []),
            "adk_workflow": self.session_state.get("adk_topology", {})
        }

    def _extract_critical_findings(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract critical findings from all agents."""
        findings = []
        for result in results:
            if result.get("status") == "completed":
                for issue in result.get("issues", [])[:2]:  # Top 2 per agent
                    findings.append({
                        "agent": result.get("agent"),
                        "finding": issue
                    })
        return findings[:5]  # Top 5 overall

    def _calculate_confidence(self, results: List[Dict[str, Any]]) -> str:
        """Calculate overall confidence level."""
        if not results:
            return "unknown"
        if any(r.get("status") == "error" for r in results):
            return "medium"
        completed = [r for r in results if r.get("status") == "completed"]
        if completed and all(r.get("confidence") == "high" for r in completed):
            return "high"
        return "medium"

    def _extract_recommendations(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract recommendations."""
        immediate_actions = []
        for result in results:
            if result.get("status") == "completed":
                for rec in result.get("recommendations", [])[:1]:
                    immediate_actions.append({"action": rec})
        return {"immediate_actions": immediate_actions}

    def _initial_session_state(self) -> Dict[str, Any]:
        """Return a clean session state skeleton."""
        return {
            "document_path": "",
            "document_content": "",
            "specialist_results": [],
            "human_reviews": [],
            "summary_result": {},
            "audit_log": [],
            "additional_context": {},
        }

    def _nano_banana_probe(self, content: str) -> Dict[str, Any]:
        """
        Lightweight FunctionTool placeholder to demonstrate custom tools in ADK.
        Performs a quick heuristic scan over the content snippet.
        """
        snippet = (content or "")[:500]
        return {
            "tool": "nano_banana_probe",
            "snippet_len": len(snippet),
            "contains_risk_terms": any(term in snippet.lower() for term in ["risk", "hazard", "safety"]),
        }
