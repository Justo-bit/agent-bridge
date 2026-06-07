"""
Agent-S3 Adapter: Converts between Coasty UI format and Agent-S orchestrator format.
Handles screenshot processing, prompt conversion, and action parsing.
"""

import base64
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ActionType(Enum):
    CLICK = "click"
    TYPE = "type"
    DRAG = "drag"
    WAIT = "wait"
    BASH = "bash"
    SCROLL = "scroll"


@dataclass
class ScreenPosition:
    """Normalized screen coordinates (0-1000 grid)."""
    x: int
    y: int

    def to_dict(self):
        return {"x": self.x, "y": self.y}


@dataclass
class Action:
    """Agent-S action output format."""
    type: ActionType
    coordinates: Optional[List[int]] = None
    text: Optional[str] = None
    bash_command: Optional[str] = None
    duration: float = 0
    reasoning: str = ""
    confidence: float = 1.0
    step: int = 0
    total_steps: int = 1

    def to_dict(self):
        result = {
            "type": self.type.value,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "step": self.step,
            "total_steps": self.total_steps,
        }
        if self.coordinates:
            result["coordinates"] = self.coordinates
        if self.text:
            result["text"] = self.text
        if self.bash_command:
            result["bash_command"] = self.bash_command
        if self.duration:
            result["duration"] = self.duration
        return result


class AgentS3Adapter:
    """Bridges Coasty UI ↔ Agent-S3 Orchestrator."""

    def __init__(self, llm_router):
        self.llm_router = llm_router
        self.screenshot_history = []
        self.action_history = []
        self.max_history = 10

    def coasty_to_agents3(
        self,
        user_prompt: str,
        screenshot_base64: Optional[str] = None,
        action_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Convert Coasty frontend input to Agent-S3 format.

        Args:
            user_prompt: Natural language instruction (e.g., "Open Slack")
            screenshot_base64: Current desktop screenshot in base64
            action_history: Previous actions taken in this session

        Returns:
            Agent-S3 compatible request dict
        """
        # Decode screenshot if provided
        screenshot = None
        if screenshot_base64:
            try:
                screenshot_data = base64.b64decode(screenshot_base64)
                screenshot = Image.open(io.BytesIO(screenshot_data))
                self.screenshot_history.append(screenshot)
            except Exception as e:
                logger.error(f"Failed to decode screenshot: {e}")

        # Format action history
        history = action_history or []
        if len(history) > self.max_history:
            history = history[-self.max_history :]

        agents3_request = {
            "objective": user_prompt,
            "screenshot": screenshot,
            "action_history": history,
            "llm_config": {
                "provider": self.llm_router.get_provider(vision_required=True).name,
                "temperature": 0.7,
                "max_tokens": 1024,
                "vision_enabled": True,
            },
            "execution_config": {
                "auto_run": True,
                "safety_check": False,
                "max_retries": 2,
            },
        }

        return agents3_request

    def agents3_to_coasty(
        self, agents3_output: Dict[str, Any], task_step: int = 1
    ) -> Dict[str, Any]:
        """
        Convert Agent-S3 action output to Coasty WebSocket format.

        Args:
            agents3_output: Raw Agent-S3 action response
            task_step: Current step number in task sequence

        Returns:
            Coasty-compatible action stream message
        """
        try:
            # Parse Agent-S3 output
            action_type = agents3_output.get("action_type", "click")
            coordinates = agents3_output.get("coordinates", [500, 500])
            text = agents3_output.get("text", "")
            reasoning = agents3_output.get("reasoning", "")
            confidence = agents3_output.get("confidence", 0.8)

            # Convert to Coasty format
            coasty_action = {
                "type": "action_stream",
                "step": task_step,
                "action": {
                    "type": action_type,
                    "coordinates": coordinates,
                    "text": text,
                },
                "metadata": {
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "timestamp": self._get_timestamp(),
                },
                "visual_feedback": self._generate_visual_feedback(
                    action_type, coordinates
                ),
                "streaming": True,
            }

            self.action_history.append(coasty_action)
            return coasty_action

        except Exception as e:
            logger.error(f"Error converting Agent-S3 output: {e}")
            return {
                "type": "error",
                "message": f"Failed to parse action: {str(e)}",
            }

    def parse_agents3_action_text(self, text: str) -> Action:
        """
        Parse Agent-S3 action text output.

        Example formats:
        - "CLICK at (500, 300)"
        - "TYPE 'password' in field"
        - "DRAG from (100, 200) to (300, 400)"
        - "WAIT 2 seconds"
        - "BASH: ls -la /tmp"
        """
        text = text.strip().upper()

        try:
            if text.startswith("CLICK"):
                coords = self._extract_coordinates(text)
                return Action(
                    type=ActionType.CLICK,
                    coordinates=coords,
                    reasoning=text,
                )

            elif text.startswith("TYPE"):
                match = self._extract_quoted_text(text)
                return Action(
                    type=ActionType.TYPE,
                    text=match,
                    reasoning=text,
                )

            elif text.startswith("DRAG"):
                coords = self._extract_coordinates(text)
                return Action(
                    type=ActionType.DRAG,
                    coordinates=coords,
                    reasoning=text,
                )

            elif text.startswith("WAIT"):
                duration = self._extract_number(text)
                return Action(
                    type=ActionType.WAIT,
                    duration=duration or 1,
                    reasoning=text,
                )

            elif text.startswith("BASH"):
                cmd = text.replace("BASH:", "").strip()
                return Action(
                    type=ActionType.BASH,
                    bash_command=cmd,
                    reasoning=text,
                )

            elif text.startswith("SCROLL"):
                direction = "down" if "DOWN" in text else "up"
                amount = self._extract_number(text) or 3
                return Action(
                    type=ActionType.SCROLL,
                    text=f"{direction}:{amount}",
                    reasoning=text,
                )

            else:
                logger.warning(f"Could not parse action: {text}")
                return Action(
                    type=ActionType.WAIT,
                    duration=1,
                    reasoning=f"Unparseable: {text}",
                )

        except Exception as e:
            logger.error(f"Error parsing action: {e}")
            return Action(
                type=ActionType.WAIT,
                duration=1,
                reasoning=f"Parse error: {str(e)}",
            )

    def _extract_coordinates(self, text: str) -> List[int]:
        """Extract (x, y) coordinates from text."""
        import re

        matches = re.findall(r"\((\d+),\s*(\d+)\)", text)
        if matches:
            x, y = matches[0]
            return [int(x), int(y)]
        return [500, 500]

    def _extract_quoted_text(self, text: str) -> str:
        """Extract quoted text."""
        import re

        matches = re.findall(r"'([^']*)'|\"([^\"]*)\"", text)
        if matches:
            return matches[0][0] or matches[0][1]
        return ""

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract first number from text."""
        import re

        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            return float(match.group(1))
        return None

    def _generate_visual_feedback(
        self, action_type: str, coordinates: List[int]
    ) -> Dict[str, Any]:
        """Generate visual feedback for Coasty UI."""
        x, y = coordinates

        feedback = {
            "highlight_box": [x - 20, y - 20, x + 20, y + 20],
            "cursor_path": [[x - 100, y - 100], [x - 50, y - 50], [x, y]],
            "annotation": f"{action_type.upper()} at ({x}, {y})",
        }

        if action_type == "type":
            feedback["highlight_box"] = [x - 100, y - 20, x + 100, y + 20]
            feedback["annotation"] = "Typing in field"
        elif action_type == "drag":
            feedback["highlight_box"] = [x - 50, y - 50, x + 50, y + 50]
            feedback["annotation"] = "Dragging element"
        elif action_type == "scroll":
            feedback["annotation"] = "Scrolling page"

        return feedback

    def _get_timestamp(self) -> str:
        """Get ISO timestamp."""
        from datetime import datetime

        return datetime.utcnow().isoformat()

    def generate_ui_tars_prompt(self, objective: str) -> str:
        """
        Generate UI-TARS system prompt with objective.
        This is what gets fed to Agent-S3's vision model.
        """
        return f"""You are an expert GUI automation agent. Your task is to complete the following objective:

OBJECTIVE: {objective}

You have access to:
- Current desktop screenshot
- Previous action history
- Natural language understanding

You must output your next action in one of these formats:
1. CLICK at (x, y) - coordinates normalized 0-1000
2. TYPE 'text content' in field
3. DRAG from (x1, y1) to (x2, y2)
4. WAIT seconds
5. BASH: shell_command
6. SCROLL UP/DOWN amount

Analyze the current screenshot carefully. Identify all interactive elements.
Choose the most logical next action to make progress toward the objective.
Be precise with coordinates. Format your response clearly.

OUTPUT:
"""

    def reset_session(self):
        """Clear session history."""
        self.screenshot_history = []
        self.action_history = []
        logger.info("Session reset")
