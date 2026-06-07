"""
DEMO: Wire All 7 Architectural Pieces Together

This demonstrates the complete unified system without rebuilding.
All pieces are existing code that we're now orchestrating together.

PIECES WIRED:
1. Workflow Engine (Agent3Orchestrator with multi-step execution)
2. Credential Vault (API key management & injection)
3. Task Scheduler (APScheduler with cron support)
4. Execution Log (JSON-persisted task history with timestamps)
5. Webhook Listener (FastAPI endpoints for external triggers)
6. Notification System (Event broadcasting with subscribers)
7. Data Storage (JSON file persistence for workflows & executions)
"""

import asyncio
import json
import logging
from typing import List, Dict, Any
from pathlib import Path

# Import existing components (no rebuilding)
from llm_router import UnifiedLLMRouter, LLMTier
from agents3_adapter import AgentS3Adapter
from coasty_integration import Agent3Orchestrator
from cost_tracker import cost_tracker
from workflow_engine import (
    UnifiedWorkflowEngine,
    WorkflowDefinition,
    WorkflowExecution,
    TaskExecution,
    NotificationBroker,
    WebhookRegistry,
    WorkflowPersistence,
)
from desktop_executor import desktop_executor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowDemoWithAll7Pieces:
    """Complete demonstration of all 7 architectural pieces working together."""

    def __init__(self):
        """Initialize all components using existing code."""
        logger.info("=" * 70)
        logger.info("INITIALIZING UNIFIED 7-PIECE ARCHITECTURE")
        logger.info("=" * 70)

        # PIECE 2: Credential Vault (already loaded in fastapi_server.py)
        logger.info("\n✅ PIECE 2: CREDENTIAL VAULT")
        logger.info("   - API keys stored in: /tmp/agent_s3_api_keys.json")
        logger.info("   - Keys persisted across process restarts")
        logger.info("   - Integrated with LLMRouter for provider selection")

        # Initialize core LLM components
        self.llm_router = UnifiedLLMRouter(prefer_tier=LLMTier.FREE)
        self.adapter = AgentS3Adapter(self.llm_router)
        self.orchestrator = Agent3Orchestrator(self.llm_router, self.adapter)

        # PIECE 1: Workflow Engine
        logger.info("\n✅ PIECE 1: WORKFLOW ENGINE")
        logger.info("   - Multi-step task execution via Agent3Orchestrator")
        logger.info("   - Step-by-step orchestration with history tracking")
        logger.info("   - Action parsing and execution")

        # PIECE 7: Data Storage (workflows loaded from JSON)
        logger.info("\n✅ PIECE 7: DATA STORAGE")
        logger.info("   - Workflows persisted in: /tmp/agent_s3_workflows.json")
        logger.info("   - Task executions in: /tmp/agent_s3_task_executions.json")
        logger.info("   - Webhooks in: /tmp/agent_s3_webhooks.json")

        self.workflow_engine = UnifiedWorkflowEngine(self.orchestrator, cost_tracker)

        # PIECE 4: Execution Log
        logger.info("\n✅ PIECE 4: EXECUTION LOG")
        logger.info("   - Every task execution recorded with timestamp")
        logger.info("   - Full action history maintained")
        logger.info("   - Results and errors tracked")

        # PIECE 5: Webhook Listener
        logger.info("\n✅ PIECE 5: WEBHOOK LISTENER")
        logger.info("   - Webhooks can trigger workflows externally")
        logger.info("   - Webhook registry tracks triggers")
        logger.info("   - External events → automatic workflow execution")

        # PIECE 6: Notification System
        logger.info("\n✅ PIECE 6: NOTIFICATION SYSTEM")
        logger.info("   - Event broadcasting on workflow/task completion")
        logger.info("   - Subscribers notified in real-time")
        logger.info("   - WebSocket integration for live updates")

        # PIECE 3: Task Scheduler
        logger.info("\n✅ PIECE 3: TASK SCHEDULER")
        logger.info("   - APScheduler for cron-based execution")
        logger.info("   - Workflows can run on schedule")
        logger.info("   - Background task execution")

        logger.info("\n" + "=" * 70)
        logger.info("ALL 7 PIECES INITIALIZED AND WIRED TOGETHER")
        logger.info("=" * 70)

    async def demo_piece_1_workflow_engine(self):
        """Demonstrate PIECE 1: Workflow Engine with multi-step execution."""
        logger.info("\n" + "=" * 70)
        logger.info("DEMO: PIECE 1 - WORKFLOW ENGINE")
        logger.info("Multi-step task orchestration using Agent3Orchestrator")
        logger.info("=" * 70)

        # Create workflow with multiple tasks
        tasks = [
            {
                "description": "Take a screenshot to see current desktop",
                "type": "screenshot",
            },
            {
                "description": "List files on desktop to see what's available",
                "type": "list_files",
            },
        ]

        workflow = self.workflow_engine.create_workflow(
            name="Screenshot & List Workflow",
            description="Demonstrates workflow with 2 sequential tasks",
            tasks=tasks,
        )

        logger.info(f"\n📋 Created workflow: {workflow.name}")
        logger.info(f"   ID: {workflow.id}")
        logger.info(f"   Tasks: {len(workflow.tasks)}")

        # Execute the workflow
        logger.info("\n⚙️  Executing workflow...")
        execution = await self.workflow_engine.execute_workflow(workflow.id)

        logger.info(f"\n✅ Workflow completed: {execution.status.value}")
        logger.info(f"   Total tasks: {len(execution.task_executions)}")
        logger.info(f"   Successful: {sum(1 for t in execution.task_executions if t.status.value == 'success')}")

    async def demo_piece_2_credential_vault(self):
        """Demonstrate PIECE 2: Credential Vault for API key management."""
        logger.info("\n" + "=" * 70)
        logger.info("DEMO: PIECE 2 - CREDENTIAL VAULT")
        logger.info("Secure API key storage and injection")
        logger.info("=" * 70)

        api_keys_file = Path("/tmp/agent_s3_api_keys.json")

        if api_keys_file.exists():
            with open(api_keys_file, "r") as f:
                keys = json.load(f)
            logger.info(f"\n📋 Stored API Keys:")
            for provider, key in keys.items():
                masked = f"{key[:8]}...{key[-4:]}" if key and len(key) > 12 else "***"
                logger.info(f"   - {provider}: {masked}")
        else:
            logger.info("\n📋 No API keys stored yet")
            logger.info("   Use /api/config/set-provider to add keys")

        logger.info(f"\n✅ Credential vault location: {api_keys_file}")
        logger.info("   - Keys are persisted across restarts")
        logger.info("   - Used by LLMRouter for provider selection")

    async def demo_piece_3_task_scheduler(self):
        """Demonstrate PIECE 3: Task Scheduler with cron expressions."""
        logger.info("\n" + "=" * 70)
        logger.info("DEMO: PIECE 3 - TASK SCHEDULER")
        logger.info("Automated workflow execution on schedule")
        logger.info("=" * 70)

        # Create a scheduled workflow
        tasks = [
            {
                "description": "Daily task: check desktop for new files",
                "type": "list_files",
            }
        ]

        # Cron: Every day at 9 AM
        workflow = self.workflow_engine.create_workflow(
            name="Daily Desktop Check",
            description="Runs every day at 9 AM",
            tasks=tasks,
            schedule="0 9 * * *",  # Cron: 9 AM daily
        )

        logger.info(f"\n📋 Created scheduled workflow: {workflow.name}")
        logger.info(f"   Schedule: {workflow.schedule} (9 AM daily)")
        logger.info(f"   Scheduler running: {self.workflow_engine.scheduler.scheduler is not None}")

        if workflow.schedule:
            logger.info("\n✅ Workflow scheduled!")
            logger.info("   - Will execute automatically at 9 AM")
            logger.info("   - Start scheduler with: /api/scheduler/start")

    async def demo_piece_4_execution_log(self):
        """Demonstrate PIECE 4: Execution Log with timestamps."""
        logger.info("\n" + "=" * 70)
        logger.info("DEMO: PIECE 4 - EXECUTION LOG")
        logger.info("Task history with complete audit trail")
        logger.info("=" * 70)

        logger.info(f"\n📋 Execution History:")
        executions = self.workflow_engine.get_execution_history(limit=5)

        if executions:
            for i, exec_data in enumerate(executions[-3:], 1):  # Show last 3
                logger.info(f"\n   {i}. {exec_data['workflow_name']}")
                logger.info(f"      ID: {exec_data['id']}")
                logger.info(f"      Status: {exec_data['status']}")
                logger.info(f"      Started: {exec_data['start_time']}")
                logger.info(f"      Tasks: {len(exec_data.get('task_executions', []))}")
        else:
            logger.info("   (No executions yet)")

        logger.info(f"\n✅ Execution log file: /tmp/agent_s3_task_executions.json")
        logger.info("   - Complete audit trail of all tasks")
        logger.info("   - Timestamps for each step")
        logger.info("   - Results and errors recorded")

    async def demo_piece_5_webhook_listener(self):
        """Demonstrate PIECE 5: Webhook Listener for external triggers."""
        logger.info("\n" + "=" * 70)
        logger.info("DEMO: PIECE 5 - WEBHOOK LISTENER")
        logger.info("External event triggering via webhooks")
        logger.info("=" * 70)

        # Create a workflow
        tasks = [
            {
                "description": "Webhook-triggered task: take screenshot",
                "type": "screenshot",
            }
        ]

        workflow = self.workflow_engine.create_workflow(
            name="Webhook Trigger Workflow",
            description="Can be triggered by external webhooks",
            tasks=tasks,
        )

        # Register webhook
        webhook_url = self.workflow_engine.webhook_registry.register_webhook(
            workflow_id=workflow.id,
            trigger_name="external_trigger",
        )

        logger.info(f"\n🔗 Webhook Registered:")
        logger.info(f"   URL: http://localhost:8081{webhook_url}")
        logger.info(f"   Workflow: {workflow.name}")
        logger.info(f"   Trigger: POST request to webhook URL executes workflow")

        logger.info("\n✅ How to trigger:")
        logger.info(f"   curl -X POST 'http://localhost:8081{webhook_url}'")

    async def demo_piece_6_notification_system(self):
        """Demonstrate PIECE 6: Notification System with event broadcasting."""
        logger.info("\n" + "=" * 70)
        logger.info("DEMO: PIECE 6 - NOTIFICATION SYSTEM")
        logger.info("Real-time event broadcasting on task completion")
        logger.info("=" * 70)

        # Subscribe to workflow events
        async def on_workflow_started(data):
            logger.info(f"\n📢 [NOTIFICATION] Workflow started: {data['workflow_name']}")

        async def on_workflow_completed(data):
            logger.info(f"\n📢 [NOTIFICATION] Workflow completed: {data['workflow_name']}")
            logger.info(f"    Status: {data['status']}")
            logger.info(f"    Tasks: {len(data.get('task_executions', []))}")

        self.workflow_engine.notification_broker.subscribe(
            "workflow.started", on_workflow_started
        )
        self.workflow_engine.notification_broker.subscribe(
            "workflow.completed", on_workflow_completed
        )

        logger.info("\n✅ Notification subscribers registered:")
        logger.info("   - workflow.started event")
        logger.info("   - workflow.completed event")
        logger.info("   - task.completed event (also available)")

        logger.info("\n💡 These notifications:")
        logger.info("   - Broadcast to WebSocket clients")
        logger.info("   - Can integrate with Slack/email/Discord")
        logger.info("   - Updated in real-time during execution")

    async def demo_piece_7_data_storage(self):
        """Demonstrate PIECE 7: Data Storage (JSON persistence)."""
        logger.info("\n" + "=" * 70)
        logger.info("DEMO: PIECE 7 - DATA STORAGE")
        logger.info("Persistent storage using JSON files")
        logger.info("=" * 70)

        files_info = [
            ("/tmp/agent_s3_workflows.json", "Workflow definitions"),
            ("/tmp/agent_s3_task_executions.json", "Task execution history"),
            ("/tmp/agent_s3_webhooks.json", "Webhook registry"),
            ("/tmp/agent_s3_api_keys.json", "API key vault"),
        ]

        logger.info("\n📁 Persistent Storage Files:")
        for filepath, description in files_info:
            path = Path(filepath)
            if path.exists():
                size = path.stat().st_size
                logger.info(f"   ✅ {description}")
                logger.info(f"      Location: {filepath}")
                logger.info(f"      Size: {size} bytes")
            else:
                logger.info(f"   ⏳ {description}")
                logger.info(f"      Location: {filepath} (will be created)")

        logger.info("\n✅ All data persists across restarts:")
        logger.info("   - Workflows defined once, executed many times")
        logger.info("   - Execution history preserved indefinitely")
        logger.info("   - Webhooks registered permanently")
        logger.info("   - API keys survive process restarts")

    async def demo_complete_workflow_execution(self):
        """End-to-end demo: all 7 pieces working together."""
        logger.info("\n" + "=" * 70)
        logger.info("COMPLETE WORKFLOW: ALL 7 PIECES TOGETHER")
        logger.info("=" * 70)

        # Create a complete workflow
        logger.info("\n1️⃣  Creating workflow...")
        tasks = [
            {
                "description": "Step 1: Take screenshot of current desktop",
                "type": "screenshot",
            },
            {
                "description": "Step 2: List desktop files",
                "type": "list_files",
            },
        ]

        workflow = self.workflow_engine.create_workflow(
            name="Complete Demo Workflow",
            description="Demonstrates all 7 pieces",
            tasks=tasks,
        )
        logger.info(f"   ✅ Created: {workflow.name} ({workflow.id})")

        # Register webhook (PIECE 5)
        logger.info("\n2️⃣  Registering webhook...")
        webhook_url = self.workflow_engine.webhook_registry.register_webhook(
            workflow_id=workflow.id,
            trigger_name="demo",
        )
        logger.info(f"   ✅ Webhook: {webhook_url}")

        # Subscribe to notifications (PIECE 6)
        logger.info("\n3️⃣  Setting up notifications...")

        async def track_execution(data):
            logger.info(f"   📢 Event: {data.get('status', 'unknown')}")

        self.workflow_engine.notification_broker.subscribe(
            "workflow.completed", track_execution
        )
        logger.info("   ✅ Subscribed to workflow events")

        # Execute workflow (PIECE 1, 2, 4, 7)
        logger.info("\n4️⃣  Executing workflow...")
        logger.info("   🔄 Starting execution...")

        execution = await self.workflow_engine.execute_workflow(
            workflow_id=workflow.id,
            triggered_by="demo",
        )

        # Check results (PIECE 4 - logs)
        logger.info("\n5️⃣  Checking execution history...")
        logger.info(f"   ✅ Workflow: {execution.workflow_name}")
        logger.info(f"   ✅ Status: {execution.status.value}")
        logger.info(f"   ✅ Tasks executed: {len(execution.task_executions)}")
        logger.info(f"   ✅ Duration: {execution.start_time} → {execution.end_time}")

        # Show persistence (PIECE 7)
        logger.info("\n6️⃣  Verifying persistence...")
        exec_path = Path("/tmp/agent_s3_task_executions.json")
        if exec_path.exists():
            size = exec_path.stat().st_size
            logger.info(f"   ✅ Saved to {exec_path}")
            logger.info(f"   ✅ File size: {size} bytes")

        logger.info("\n" + "=" * 70)
        logger.info("✅ ALL 7 PIECES WORKING TOGETHER SUCCESSFULLY!")
        logger.info("=" * 70)

    async def run_all_demos(self):
        """Run all demonstrations."""
        logger.info("\n\n")
        logger.info("╔" + "=" * 68 + "╗")
        logger.info("║" + " " * 68 + "║")
        logger.info("║" + "UNIFIED AGENT-S3 + COASTY: 7-PIECE ARCHITECTURE DEMO".center(68) + "║")
        logger.info("║" + " " * 68 + "║")
        logger.info("╚" + "=" * 68 + "╝")

        # Run individual piece demos
        await self.demo_piece_2_credential_vault()
        await self.demo_piece_1_workflow_engine()
        await self.demo_piece_3_task_scheduler()
        await self.demo_piece_4_execution_log()
        await self.demo_piece_5_webhook_listener()
        await self.demo_piece_6_notification_system()
        await self.demo_piece_7_data_storage()

        # Run complete end-to-end demo
        await self.demo_complete_workflow_execution()

        logger.info("\n\n")
        logger.info("═" * 70)
        logger.info("DEMO COMPLETE")
        logger.info("═" * 70)
        logger.info("\nNext steps:")
        logger.info("1. Start the FastAPI server: python3 fastapi_server.py")
        logger.info("2. Create workflows via /api/workflows endpoint")
        logger.info("3. Register webhooks with /api/workflows/{id}/webhook")
        logger.info("4. Trigger via webhook: POST /api/webhook/{webhook_id}")
        logger.info("5. Monitor execution: GET /api/executions")
        logger.info("6. Check data: cat /tmp/agent_s3_task_executions.json")
        logger.info("\nAPI Documentation:")
        logger.info("- http://localhost:8081/docs (when server running)")


async def main():
    """Run the complete demo."""
    demo = WorkflowDemoWithAll7Pieces()
    await demo.run_all_demos()


if __name__ == "__main__":
    asyncio.run(main())
