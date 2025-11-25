#!/usr/bin/env python3
"""
Simple Advanced MVP Demo for Multi-Agent Compliance Reviewer

Demonstrates:
- Parallel execution of specialist agents (ParallelAgent pattern)
- Human-in-the-loop with asyncio (LoopAgent pattern)
- Structured operations with proper error handling
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env for local runs
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from coordinator_simple import SimpleAdvancedCoordinator


async def demo_advanced_workflow():
    """
    Run the simple advanced demo workflow.
    """
    print("=" * 70)
    print("ADVANCED MULTI-AGENT COMPLIANCE REVIEWER FOR MEDICAL DEVICES")
    print("Using Google ADK: Parallel Agents and Human-in-the-Loop")
    print("=" * 70)
    print()

    # Initialize advanced coordinator
    try:
        coordinator = SimpleAdvancedCoordinator()
        print("✓ Advanced Compliance Coordinator initialized")
        print("  - Parallel execution of specialist agents")
        print("  - Human-in-the-loop integration patterns")
        print("  - Comprehensive audit logging")
        print()
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Create sample document
    sample_content = """
    MEDICAL DEVICE REQUIREMENTS DOCUMENT

    1. GENERAL REQUIREMENTS
    1.1 The device shall be biocompatible according to ISO 10993.
    1.2 The system shall meet cybersecurity requirements per IEC 62304.
    1.3 Device shall operate within temperature range of 5-40°C.

    2. SAFETY REQUIREMENTS
    2.1 System shall prevent unintended activation.
    2.2 Software shall handle error conditions gracefully.
    2.3 Device shall include emergency stop functionality.

    3. PERFORMANCE REQUIREMENTS
    3.1 Response time shall be < 5 seconds.
    3.2 Accuracy shall be > 95%.
    3.3 Power consumption shall be < 50W.

    4. DESIGN CONTROLS
    4.1 All changes shall be documented.
    4.2 Verification testing shall be completed.
    4.3 Validation shall confirm user needs met.

    5. RISK MANAGEMENT
    5.1 Hazard analysis shall identify all potential risks.
    5.2 Risk control measures shall reduce risks to acceptable levels.
    5.3 Residual risks shall be acceptable per ISO 14971.
    """

    # Save sample document
    sample_path = "data/sample_medical_device_requirements.txt"
    os.makedirs("data", exist_ok=True)

    with open(sample_path, "w") as f:
        f.write(sample_content.strip())

    print(f"✓ Sample requirements document created: {sample_path}")
    print()

    # Process the document with advanced workflow
    print("🔍 Starting PARALLEL compliance analysis...")
    print("   - Running 4 specialist agents concurrently")
    print("   - Evaluating for human-in-the-loop needs")
    print("   - Building comprehensive audit trail")
    print()

    try:
        # Process document with advanced coordinator
        results = await coordinator.process_document(
            sample_path,
            additional_context={
                "device_class": "Class II medical device",
                "intended_use": "Patient monitoring in clinical settings",
                "regulatory_path": "FDA 510(k) submission"
            }
        )

        # Display results
        if results.get("status") == "completed":
            print("✅ PARALLEL COMPLIANCE ANALYSIS COMPLETED")
            print()

            # Summary
            metadata = results.get("metadata", {})
            print("📊 EXECUTION SUMMARY:")
            print(f"Coordinator: {metadata.get('coordinator', 'Unknown')}")
            print(f"Specialist Agents (Parallel): {metadata.get('total_specialist_agents', 0)}")
            print(f"Human Reviews Triggered: {metadata.get('human_reviews_triggered', 0)}")
            print(f"Processing Timestamp: {metadata.get('processing_timestamp', 'Unknown')}")
            print()

            # Compliance summary
            summary = results.get("compliance_summary", {})
            print("📋 COMPLIANCE STATUS:")
            print(f"Overall Status: {summary.get('overall_compliance_status', 'Unknown').upper()}")
            print(f"Critical Findings: {len(summary.get('critical_findings', []))}")
            print(f"Confidence Level: {summary.get('confidence_level', 'Unknown')}")
            print()

            # Specialist analyses
            analyses = results.get("specialist_analyses", [])
            print("🤖 SPECIALIST AGENTS ANALYSIS (Parallel Execution):")
            for analysis in analyses:
                agent_name = analysis.get("agent", "Unknown Agent")
                status = analysis.get("status", "unknown")
                issues = len(analysis.get("issues", []))
                confidence = analysis.get("confidence", "unknown")
                print(f"  • {agent_name}: {status} ({issues} issues, confidence: {confidence})")

            print()

            # Human-in-the-loop status
            human_loop = results.get("human_in_loop", {})
            pending = len(human_loop.get("pending_reviews", []))
            completed = len(human_loop.get("completed_reviews", []))

            print("👤 HUMAN-IN-THE-LOOP STATUS (LoopAgent Pattern):")
            print(f"  Pending Reviews: {pending}")
            print(f"  Completed Reviews: {completed}")
            print()

            # Recommendations
            recommendations = results.get("recommendations", {})
            immediate = recommendations.get("immediate_actions", [])
            if immediate:
                print("🚨 IMMEDIATE ACTIONS REQUIRED:")
                for rec in immediate:
                    print(f"  • {rec.get('action', 'Unknown action')}")
                print()

            # Audit trail
            audit = results.get("audit_trail", [])
            print(f"📝 AUDIT TRAIL: {len(audit)} entries")
            print()

            # Save detailed report
            report_path = "data/compliance_report_parallel.json"
            with open(report_path, "w") as f:
                json.dump(results, f, indent=2)

            print(f"💾 Detailed report saved to: {report_path}")
            print()

            # Demo human-in-the-loop if needed
            if pending > 0:
                print("🎯 DEMO: Simulating human review process...")
                await demo_human_loop(coordinator, results)

        else:
            print("❌ ANALYSIS FAILED")
            error_msg = results.get("error_message", "Unknown error")
            print(f"Error: {error_msg}")

    except Exception as e:
        print(f"❌ PROCESSING ERROR: {e}")
        import traceback
        traceback.print_exc()


async def demo_human_loop(coordinator, results):
    """
    Demonstrate the human-in-the-loop process.
    """
    print("\n--- HUMAN-IN-THE-LOOP LOOP AGENT SIMULATION ---")

    human_loop = results.get("human_in_loop", {})
    pending_reviews = human_loop.get("pending_reviews", [])

    if not pending_reviews:
        print("No pending reviews to process")
        return

    # Simulate human decisions
    human_decisions = []
    for review in pending_reviews:
        decision = {
            "review_id": review.get("request_id"),
            "decision": "accept",
            "justification": "Requirements are adequately covered per FDA guidance"
        }
        human_decisions.append(decision)

    # Resume with human decisions
    print(f"Processing {len(human_decisions)} human decisions...")
    updated_report = await coordinator.resume_with_human_feedback(human_decisions)

    print("✓ Human feedback incorporated")
    print(f"✓ Updated report status: {updated_report.get('status')}")
    print("✓ Audit trail updated with human decisions")
    print()


def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print("  python main_simple_adv.py                    # Run advanced demo")
    print()
    print("Advanced Features:")
    print("  - Parallel Execution: Concurrent specialist agent analysis")
    print("  - Human-in-the-Loop: LoopAgent pattern with asyncio")
    print("  - Audit Logging: Complete trace of all decisions")
    print()
    print("Requirements:")
    print("  - Google Cloud Gemini API access")
    print("  - Configure GEMINI_API_KEY environment variable")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
    else:
        # Run the advanced demo
        asyncio.run(demo_advanced_workflow())

        print("\n" + "=" * 70)
        print("ADVANCED DEMO COMPLETE")
        print("This demonstration showcases Google ADK patterns:")
        print("  ✓ Parallel execution of multiple specialist agents")
        print("  ✓ Human-in-the-loop workflow with LoopAgent pattern")
        print("  ✓ Comprehensive audit logging for compliance")
        print()
        print("For production deployment:")
        print("  - Configure proper authentication and state persistence")
        print("  - Implement database storage for session state")
        print("  - Add comprehensive monitoring and logging")
        print("  - Set up human approval workflows with notification systems")
        print("=" * 70)
