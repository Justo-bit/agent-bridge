"""
Coasty ↔ Agent-S3 Integration Layer
Bridges Coasty's multi_agent_executor with Agent-S3 backend.
Intercepts task execution and routes through Agent-S3 orchestrator.
"""

import asyncio
import json
import logging
import base64
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime
from enum import Enum

from llm_router import UnifiedLLMRouter, LLMTier
from agents3_adapter import AgentS3Adapter, ActionType

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Agent types that match Coasty's agent system."""
    BROWSER = "browser"
    TERMINAL = "terminal"
    DESKTOP = "desktop"
    SEARCH = "search"


class CoastyAgent(Enum):
    """Specialized agent roles."""
    PLANNER = "planner"
    BROWSER = "browser"
    TERMINAL = "terminal"
    DESKTOP = "desktop"


class Agent3Orchestrator:
    """
    Replaces Coasty's multi_agent_executor with Agent-S3 orchestration.
    Maintains Coasty's API contract while leveraging Agent-S3's power.
    """

    def __init__(self, llm_router: UnifiedLLMRouter, adapter: AgentS3Adapter):
        self.llm_router = llm_router
        self.adapter = adapter
        self.execution_history = []
        self.max_history = 5

    async def execute_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        screenshot: Optional[bytes] = None,
        tools: Optional[List[str]] = None,
        task_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a task using Agent-S3 orchestration.
        Streams results back to Coasty in compatible format.

        Args:
            task: User's objective (e.g., "Open Slack and find messages")
            context: Previous task results and context
            screenshot: Current desktop screenshot
            tools: Available tools for this agent
            task_id: Unique task identifier for cost tracking

        Yields:
            Streaming events compatible with Coasty's format:
            {
                "type": "thinking" | "text" | "tool_call" | "tool_result" | "finish",
                "data": {...}
            }
        """
        logger.info(f"📡 Starting Agent-S3 orchestration for: {task[:50]}...")

        # Prepare Agent-S3 context
        context = context or {}
        if task_id:
            context["task_id"] = task_id
        screenshot_b64 = None
        if screenshot:
            screenshot_b64 = base64.b64encode(screenshot).decode()

        # Get best LLM provider
        provider = self.llm_router.get_provider(vision_required=screenshot_b64 is not None)
        logger.info(f"📊 Using provider: {provider.name}")

        # Convert to Agent-S3 format
        agents3_request = self.adapter.coasty_to_agents3(
            user_prompt=task,
            screenshot_base64=screenshot_b64,
            action_history=self._format_history_for_agent(),
        )

        # Execute via Agent-S3
        step = 1
        max_steps = 10

        try:
            while step <= max_steps:
                # Generate next action via LLM
                action_response = await self._invoke_llm(
                    llm_router=self.llm_router,
                    provider=provider,
                    task=task,
                    screenshot=screenshot,
                    context=context,
                    step=step,
                    max_steps=max_steps,
                )

                # Emit thinking/reasoning
                if "reasoning" in action_response:
                    yield {
                        "type": "thinking",
                        "data": {
                            "text": action_response["reasoning"],
                            "step": step,
                            "total_steps": max_steps,
                        },
                    }

                # Parse action
                action = self.adapter.parse_agents3_action_text(
                    action_response.get("action", "WAIT 1")
                )

                # Emit action (tool call)
                yield {
                    "type": "tool_call",
                    "data": {
                        "tool": action.type.value,
                        "args": {
                            "coordinates": action.coordinates,
                            "text": action.text,
                            "bash_command": action.bash_command,
                            "duration": action.duration,
                        },
                        "step": step,
                    },
                }

                # Execute action and capture result
                execution_result = await self._execute_action(action, screenshot)

                # Emit result
                yield {
                    "type": "tool_result",
                    "data": {
                        "tool": action.type.value,
                        "result": execution_result,
                        "step": step,
                    },
                }

                # Store in history
                self.execution_history.append(
                    {
                        "step": step,
                        "action": action.type.value,
                        "result": execution_result,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

                # Check if task complete
                if execution_result.get("status") == "complete":
                    yield {
                        "type": "finish",
                        "data": {
                            "message": execution_result.get("message", "Task completed"),
                            "total_steps": step,
                            "success": True,
                        },
                    }
                    break

                step += 1

                # Small delay between steps
                await asyncio.sleep(0.5)

            # Max steps reached
            if step > max_steps:
                yield {
                    "type": "finish",
                    "data": {
                        "message": f"Reached maximum steps ({max_steps})",
                        "total_steps": step,
                        "success": False,
                    },
                }

        except Exception as e:
            logger.error(f"❌ Orchestration failed: {e}")
            yield {
                "type": "error",
                "data": {
                    "message": f"Execution failed: {str(e)}",
                    "error_type": type(e).__name__,
                },
            }

    async def _invoke_llm(
        self,
        llm_router: UnifiedLLMRouter,
        provider,
        task: str,
        screenshot: Optional[bytes],
        context: Dict[str, Any],
        step: int,
        max_steps: int,
    ) -> Dict[str, Any]:
        """
        Invoke Agent-S3's LLM to generate next action.
        """
        # Build prompt with context
        prompt = self._build_action_prompt(
            task=task,
            context=context,
            step=step,
            max_steps=max_steps,
            execution_history=self.execution_history,
        )

        # Call LLM (with task_id for cost tracking)
        result = llm_router.route_completion(
            prompt=prompt,
            system_prompt=self.adapter.generate_ui_tars_prompt(task),
            vision_data=screenshot,
            max_tokens=512,
            task_id=context.get("task_id"),
        )

        logger.debug(f"LLM response: {result['response'][:100]}...")

        return {
            "action": result["response"],
            "reasoning": f"Step {step}: Analyzed screenshot and generated action",
            "provider": result["provider"],
        }

    def _build_action_prompt(
        self,
        task: str,
        context: Dict[str, Any],
        step: int,
        max_steps: int,
        execution_history: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for Agent-S3 to generate next action."""
        prompt = f"""You are an expert GUI automation agent. Step {step}/{max_steps}.

USER OBJECTIVE: {task}

PREVIOUS ACTIONS:
"""
        for i, entry in enumerate(execution_history[-3:], 1):  # Last 3 actions
            prompt += f"\n{i}. {entry['action']} → {entry['result'].get('status', 'unknown')}"

        prompt += f"""

CONTEXT:
- Current step: {step}/{max_steps}
- Available tools: click, type, drag, bash, scroll, wait
- Screenshot analyzed

NEXT ACTION:
Output your next action in one of these formats:
- CLICK at (x, y)
- TYPE 'text'
- DRAG from (x1, y1) to (x2, y2)
- BASH: command
- SCROLL UP/DOWN amount
- WAIT seconds

Be precise. Analyze the screenshot. Choose the most logical next step.
"""
        return prompt

    async def _execute_action(
        self, action, screenshot: Optional[bytes]
    ) -> Dict[str, Any]:
        """
        Execute the generated action.
        In production, this calls actual desktop automation (pyautogui, etc).
        For testing, we simulate the action.
        """
        logger.info(f"Executing: {action.type.value} at {action.coordinates}")

        # Simulate action execution
        result = {
            "status": "executed",
            "action": action.type.value,
            "coordinates": action.coordinates,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add action-specific results
        if action.type == ActionType.CLICK:
            result["message"] = f"Clicked at {action.coordinates}"
        elif action.type == ActionType.TYPE:
            result["message"] = f"Typed: {action.text}"
        elif action.type == ActionType.WAIT:
            await asyncio.sleep(action.duration)
            result["message"] = f"Waited {action.duration}s"
        elif action.type == ActionType.BASH:
            result["message"] = f"Executed: {action.bash_command}"
        elif action.type == ActionType.SCROLL:
            result["message"] = f"Scrolled: {action.text}"

        return result

    def _format_history_for_agent(self) -> List[Dict[str, Any]]:
        """Format execution history for Agent-S3."""
        if len(self.execution_history) > self.max_history:
            history = self.execution_history[-self.max_history :]
        else:
            history = self.execution_history

        return [
            {
                "step": h["step"],
                "action": h["action"],
                "result": h["result"].get("message", ""),
            }
            for h in history
        ]

    def reset(self):
        """Reset orchestration state for new session."""
        self.execution_history = []
        self.adapter.reset_session()
        logger.info("Orchestrator reset")


class CoastyBackendIntegration:
    """
    Replaces Coasty's multi_agent_executor module.
    Drop-in replacement that delegates to Agent-S3.
    """

    def __init__(self):
        self.llm_router = UnifiedLLMRouter(prefer_tier=LLMTier.FREE)
        self.adapter = AgentS3Adapter(self.llm_router)
        self.orchestrator = Agent3Orchestrator(self.llm_router, self.adapter)

    async def execute_multi_agent_task(
        self,
        user_message: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        user_files: Optional[List[str]] = None,
        screenshot: Optional[bytes] = None,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Drop-in replacement for Coasty's multi_agent_executor.execute_task.

        Signature matches Coasty's API:
        - Accepts user_message (task description)
        - Accepts chat_history for context
        - Returns async generator of streaming events
        - Events compatible with Coasty's format

        Yields:
            {
                "type": "thinking" | "tool_call" | "tool_result" | "text" | "finish" | "error",
                "data": {...}
            }
        """
        # Generate task ID if not provided (for cost tracking)
        if not task_id:
            task_id = str(uuid.uuid4())[:8]

        logger.info(f"🤖 Coasty Integration: Starting Agent-S3 task [{task_id}]")

        # Build context from chat history
        context = {"task_id": task_id}
        if chat_history:
            for msg in chat_history[-3:]:  # Last 3 messages for context
                if msg.get("role") == "assistant":
                    context[f"previous_response_{len(context)}"] = msg.get("content", "")

        # Emit initial status
        yield {
            "type": "thinking",
            "data": {
                "text": f"🚀 Starting Agent-S3 orchestration...\n📊 Using provider: {self.llm_router.get_provider(vision_required=screenshot is not None).name}\n📊 Task ID: {task_id}",
            },
        }

        # Execute via Agent-S3 orchestrator
        async for event in self.orchestrator.execute_task(
            task=user_message,
            context=context,
            screenshot=screenshot,
            task_id=task_id,
        ):
            yield event

    async def stream_agent_response(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Stream-compatible LLM response.
        Matches Coasty's streaming interface.
        """
        provider = self.llm_router.get_provider()
        result = self.llm_router.route_completion(
            prompt=messages[-1]["content"],
            system_prompt=messages[0]["content"] if messages else "",
            max_tokens=1024,
        )

        # Stream response character by character
        for char in result["response"]:
            yield char
            await asyncio.sleep(0.01)  # Simulate streaming delay

    def get_available_agents(self) -> List[Dict[str, str]]:
        """Get available agent types (matches Coasty API)."""
        return [
            {
                "id": "agent_s3_planner",
                "name": "Agent-S3 Planner",
                "description": "AI-powered task planning and orchestration",
                "type": "planner",
            },
            {
                "id": "agent_s3_browser",
                "name": "Agent-S3 Browser",
                "description": "Browser automation and web interaction",
                "type": "browser",
            },
            {
                "id": "agent_s3_desktop",
                "name": "Agent-S3 Desktop",
                "description": "Desktop GUI automation",
                "type": "desktop",
            },
            {
                "id": "agent_s3_terminal",
                "name": "Agent-S3 Terminal",
                "description": "Command execution and file operations",
                "type": "terminal",
            },
        ]

    def get_llm_config(self) -> Dict[str, Any]:
        """Get current LLM configuration."""
        return {
            "provider_tier": self.llm_router.prefer_tier.value,
            "available_providers": self.llm_router.get_stats(),
        }

    def set_llm_tier(self, tier: str) -> bool:
        """Switch LLM tier (free/paid)."""
        if tier == "free":
            self.llm_router.prefer_tier = LLMTier.FREE
            return True
        elif tier == "paid":
            self.llm_router.prefer_tier = LLMTier.PAID
            return True
        return False


# Singleton instance for Coasty backend integration
coasty_agent_s3 = CoastyBackendIntegration()
