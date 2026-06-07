"""
Approval System - Enterprise governance for automation workflows
Integrates ApprovalManager from Coasty with Unified Workflow Engine

MODES:
- full_control: All actions auto-approved (development/testing)
- smart_approve: Read-only operations auto-approved, dangerous actions require approval
- approve_all: Every action requires manual approval (high-security)
- off: All actions denied (disabled mode)

SAFE_COMMANDS (auto-approved in smart_approve mode):
- screenshot, browser_screenshot, browser_state, browser_get_dom
- file_read, file_exists, directory_list
- terminal_read, terminal_connect
- list_windows, browser_list_tabs
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from datetime import datetime
import json
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

# File for persisting approval config
APPROVAL_CONFIG_FILE = Path("/tmp/agent_s3_approval_config.json")

# Read-only / safe operations that don't modify state
SAFE_COMMANDS = {
    'screenshot',
    'browser_screenshot',
    'browser_state',
    'browser_get_dom',
    'browser_get_clickables',
    'browser_info',
    'file_read',
    'file_exists',
    'directory_list',
    'file_list_downloads',
    'terminal_read',
    'terminal_connect',
    'list_windows',
    'browser_list_tabs',
    'get_state',
}

# Dangerous operations that should require approval
DANGEROUS_COMMANDS = {
    'execute_command',
    'create_file',
    'delete_file',
    'open_application',
    'click',
    'type_text',
    'press_key',
    'browser_navigate',
    'browser_click',
    'browser_type',
    'browser_execute_script',
    'browser_wait_for',
}


class ApprovalMode(str, Enum):
    """Approval workflow modes"""
    FULL_CONTROL = "full_control"      # Auto-approve everything
    SMART_APPROVE = "smart_approve"    # Auto-approve safe, require dangerous
    APPROVE_ALL = "approve_all"        # Require approval for everything
    OFF = "off"                        # Deny everything


class ApprovalRequest:
    """Represents a request for approval"""

    def __init__(self, command: str, parameters: Dict[str, Any], task_id: str = None):
        self.id = f"approval_{uuid.uuid4().hex[:8]}"
        self.command = command
        self.parameters = parameters
        self.task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        self.created_at = datetime.utcnow().isoformat()
        self.status = "pending"  # pending, approved, denied
        self.approved_by = None
        self.approved_at = None
        self.reason = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "parameters": self.parameters,
            "task_id": self.task_id,
            "created_at": self.created_at,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "reason": self.reason,
        }


class ApprovalManager:
    """
    Manages approval workflows for automation tasks

    Determines which actions need approval based on mode and command type
    """

    def __init__(self):
        """Initialize approval manager"""
        self.mode = ApprovalMode.SMART_APPROVE
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_history: List[ApprovalRequest] = []
        self.max_history = 1000
        self.approval_callbacks: Dict[str, Callable] = {}

        self.load_config()
        logger.info(f"✅ ApprovalManager initialized (mode: {self.mode.value})")

    def get_mode(self) -> str:
        """Get current approval mode"""
        return self.mode.value

    def set_mode(self, mode: str) -> bool:
        """Set approval mode"""
        try:
            self.mode = ApprovalMode(mode)
            self.save_config()
            logger.info(f"✅ Approval mode changed to: {mode}")
            return True
        except ValueError:
            logger.error(f"❌ Invalid mode: {mode}")
            return False

    def should_require_approval(self, command: str) -> bool:
        """
        Determine if a command requires approval based on current mode

        Returns:
            True if approval is required, False if auto-approved
        """
        if self.mode == ApprovalMode.FULL_CONTROL:
            return False  # Auto-approve everything

        if self.mode == ApprovalMode.OFF:
            return True  # Require approval (will be denied)

        if self.mode == ApprovalMode.APPROVE_ALL:
            return True  # Require approval for everything

        if self.mode == ApprovalMode.SMART_APPROVE:
            # Auto-approve safe commands, require dangerous ones
            return command not in SAFE_COMMANDS

        return False

    def request_approval(self, command: str, parameters: Dict[str, Any], task_id: str = None) -> ApprovalRequest:
        """
        Create an approval request for a command

        Returns:
            ApprovalRequest object with status
        """
        approval = ApprovalRequest(command, parameters, task_id)
        self.pending_approvals[approval.id] = approval

        logger.info(f"🔒 Approval requested: {command} (id: {approval.id})")
        logger.info(f"   Task: {task_id}")
        logger.info(f"   Mode: {self.mode.value}")
        logger.info(f"   Safe: {command in SAFE_COMMANDS}")

        return approval

    def approve(self, approval_id: str, approved_by: str = "admin", reason: str = None) -> bool:
        """Approve a pending request"""
        if approval_id not in self.pending_approvals:
            logger.warning(f"⚠️  Approval not found: {approval_id}")
            return False

        approval = self.pending_approvals.pop(approval_id)
        approval.status = "approved"
        approval.approved_by = approved_by
        approval.approved_at = datetime.utcnow().isoformat()
        approval.reason = reason

        self.approval_history.append(approval)
        if len(self.approval_history) > self.max_history:
            self.approval_history = self.approval_history[-self.max_history:]

        logger.info(f"✅ Approved: {approval.command} by {approved_by}")
        return True

    def deny(self, approval_id: str, denied_by: str = "admin", reason: str = None) -> bool:
        """Deny a pending request"""
        if approval_id not in self.pending_approvals:
            logger.warning(f"⚠️  Approval not found: {approval_id}")
            return False

        approval = self.pending_approvals.pop(approval_id)
        approval.status = "denied"
        approval.approved_by = denied_by
        approval.approved_at = datetime.utcnow().isoformat()
        approval.reason = reason

        self.approval_history.append(approval)

        logger.info(f"❌ Denied: {approval.command} by {denied_by}")
        return True

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all pending approval requests"""
        return [approval.to_dict() for approval in self.pending_approvals.values()]

    def get_approval_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent approval history"""
        return [approval.to_dict() for approval in self.approval_history[-limit:]]

    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get specific approval request (pending or history)"""
        if approval_id in self.pending_approvals:
            return self.pending_approvals[approval_id].to_dict()

        for approval in self.approval_history:
            if approval.id == approval_id:
                return approval.to_dict()

        return None

    def subscribe_to_approvals(self, callback: Callable):
        """Subscribe to approval notifications"""
        callback_id = f"callback_{uuid.uuid4().hex[:8]}"
        self.approval_callbacks[callback_id] = callback
        logger.info(f"📢 Approval callback registered: {callback_id}")
        return callback_id

    def save_config(self):
        """Persist approval config to file"""
        try:
            config = {
                "mode": self.mode.value,
                "saved_at": datetime.utcnow().isoformat(),
            }
            with open(APPROVAL_CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"💾 Approval config saved: {self.mode.value}")
        except Exception as e:
            logger.error(f"❌ Failed to save config: {e}")

    def load_config(self):
        """Load approval config from file"""
        try:
            if APPROVAL_CONFIG_FILE.exists():
                with open(APPROVAL_CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.mode = ApprovalMode(config.get("mode", "smart_approve"))
                logger.info(f"📂 Approval config loaded: {self.mode.value}")
            else:
                logger.info("📂 No approval config found, using defaults")
        except Exception as e:
            logger.error(f"⚠️  Failed to load config: {e}")
            self.mode = ApprovalMode.SMART_APPROVE

    def get_stats(self) -> Dict[str, Any]:
        """Get approval statistics"""
        approved = sum(1 for a in self.approval_history if a.status == "approved")
        denied = sum(1 for a in self.approval_history if a.status == "denied")

        return {
            "current_mode": self.mode.value,
            "pending_count": len(self.pending_approvals),
            "total_approved": approved,
            "total_denied": denied,
            "history_size": len(self.approval_history),
            "safe_commands_count": len(SAFE_COMMANDS),
            "dangerous_commands_count": len(DANGEROUS_COMMANDS),
        }


# Singleton instance
approval_manager = ApprovalManager()
