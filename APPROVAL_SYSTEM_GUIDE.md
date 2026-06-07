# Approval System Implementation Guide

## Overview

Enterprise-grade governance system for automated workflows. Classifies commands as safe or dangerous and enforces approval policies based on configurable modes.

## Architecture

### ApprovalManager Class
Core governance engine that determines whether commands require approval before execution.

**Key Properties:**
- `mode`: Current approval mode (full_control, smart_approve, approve_all, off)
- `pending_approvals`: Dict of requests awaiting decision
- `approval_history`: Audit trail of all approval decisions
- `max_history`: Keeps last 1000 approvals for audit

### Approval Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **full_control** | Auto-approve all commands | Development & testing |
| **smart_approve** | Auto-approve safe ops, require dangerous | Production default |
| **approve_all** | Require approval for everything | High-security environments |
| **off** | Deny all actions | Disabled/maintenance mode |

### Command Classification

**Safe Commands (15 total)** - Auto-approved in smart_approve mode:
- Read-only operations: `screenshot`, `file_read`, `directory_list`, `browser_get_dom`
- Status checks: `browser_state`, `get_state`, `browser_info`
- Lists: `file_exists`, `file_list_downloads`, `list_windows`, `browser_list_tabs`
- Connectivity: `terminal_read`, `terminal_connect`
- Browser screenshot: `browser_screenshot`

**Dangerous Commands (12 total)** - Require approval:
- Execution: `execute_command`
- File ops: `create_file`, `delete_file`
- Applications: `open_application`
- Browser: `browser_navigate`, `browser_click`, `browser_type`, `browser_execute_script`, `browser_wait_for`
- Input: `click`, `type_text`, `press_key`

## API Endpoints

### 1. Get Current Mode
```bash
GET /api/approval/mode
```
**Response:**
```json
{
  "mode": "smart_approve",
  "modes_available": ["full_control", "smart_approve", "approve_all", "off"],
  "description": "full_control (auto-all) | smart_approve (safe-auto) | approve_all (require-all) | off (deny-all)"
}
```

### 2. Set Approval Mode
```bash
POST /api/approval/mode?mode=approve_all
```
**Parameters:**
- `mode`: One of the four modes

**Response:**
```json
{
  "success": true,
  "mode": "approve_all",
  "error": null
}
```

### 3. Request Approval
```bash
POST /api/approval/request?command=execute_command&task_id=automation_001
```
**Parameters:**
- `command`: Command name to request approval for
- `parameters`: (optional) Command parameters as JSON
- `task_id`: (optional) Associated task ID

**Response:**
```json
{
  "id": "approval_797af862",
  "command": "execute_command",
  "parameters": {},
  "task_id": "automation_001",
  "created_at": "2026-06-07T21:28:15.810256",
  "status": "pending",
  "approved_by": null,
  "approved_at": null,
  "reason": null
}
```

### 4. Approve Request
```bash
POST /api/approval/{approval_id}/approve?approved_by=admin&reason=verified
```
**Parameters:**
- `approval_id`: (path) Approval request ID
- `approved_by`: User who approved
- `reason`: (optional) Approval reason

**Response:**
```json
{
  "success": true,
  "approval_id": "approval_797af862",
  "action": "approved",
  "approval": { /* full approval object */ }
}
```

### 5. Deny Request
```bash
POST /api/approval/{approval_id}/deny?denied_by=admin&reason=security_concern
```
**Parameters:**
- `approval_id`: (path) Approval request ID
- `denied_by`: User who denied
- `reason`: (optional) Denial reason

**Response:**
```json
{
  "success": true,
  "approval_id": "approval_797af862",
  "action": "denied",
  "approval": { /* full approval object */ }
}
```

### 6. Get Pending Approvals
```bash
GET /api/approval/pending
```
**Response:**
```json
{
  "pending_count": 1,
  "approvals": [
    {
      "id": "approval_797af862",
      "command": "execute_command",
      "parameters": {},
      "task_id": "automation_001",
      "created_at": "2026-06-07T21:28:15.810256",
      "status": "pending",
      "approved_by": null,
      "approved_at": null,
      "reason": null
    }
  ]
}
```

### 7. Get Approval History
```bash
GET /api/approval/history?limit=50
```
**Parameters:**
- `limit`: Number of recent approvals to return

**Response:**
```json
{
  "limit": 50,
  "history_count": 1,
  "history": [
    {
      "id": "approval_797af862",
      "command": "execute_command",
      "parameters": {},
      "task_id": "automation_001",
      "created_at": "2026-06-07T21:28:15.810256",
      "status": "approved",
      "approved_by": "admin",
      "approved_at": "2026-06-07T21:28:16.012604",
      "reason": "verified"
    }
  ]
}
```

### 8. Check Command Classification
```bash
GET /api/approval/should-approve?command=execute_command
```
**Response:**
```json
{
  "command": "execute_command",
  "requires_approval": true,
  "current_mode": "smart_approve",
  "is_safe_command": false
}
```

### 9. Get Statistics
```bash
GET /api/approval/stats
```
**Response:**
```json
{
  "current_mode": "smart_approve",
  "pending_count": 0,
  "total_approved": 5,
  "total_denied": 1,
  "history_size": 6,
  "safe_commands_count": 15,
  "dangerous_commands_count": 12
}
```

## Integration with Workflows

### Workflow Execution with Approval Gate

When executing a workflow task:

1. **Check if approval needed:**
   ```python
   needs_approval = approval_manager.should_require_approval(command)
   ```

2. **Request approval if needed:**
   ```python
   if needs_approval:
       approval = approval_manager.request_approval(
           command=command,
           parameters=params,
           task_id=workflow_task_id
       )
       # Wait for approval decision
       # Don't execute until approved
   ```

3. **Execute after approval:**
   ```python
   # Only execute if mode is full_control
   # or if approval was granted
   if approval_manager.mode == ApprovalMode.FULL_CONTROL or approval.status == "approved":
       execute_command(command, parameters)
   ```

## Persistence

Approval configuration persists to `/tmp/agent_s3_approval_config.json`:

```json
{
  "mode": "smart_approve",
  "saved_at": "2026-06-08T10:30:00.000000"
}
```

Approval requests are stored in memory and persists across the session lifetime.

## Use Cases

### Use Case 1: Development Environment
```bash
# Enable auto-approval for rapid testing
POST /api/approval/mode?mode=full_control
```
All commands execute without approval delays.

### Use Case 2: Production Automation
```bash
# Enable smart approval (default)
POST /api/approval/mode?mode=smart_approve
```
- Read operations (screenshots, file reads) auto-execute
- Dangerous operations (executing commands, file writes) require approval
- Each operation is tracked in history

### Use Case 3: High-Security Workflows
```bash
# Require approval for all operations
POST /api/approval/mode?mode=approve_all
```
Every command, even safe ones, requires manual approval.

### Use Case 4: Emergency Disable
```bash
# Disable all automation
POST /api/approval/mode?mode=off
```
No commands execute; all approvals return denied.

## Audit Trail

Every approval decision is logged with:
- `id`: Unique request ID
- `command`: Command being approved
- `parameters`: Command parameters
- `task_id`: Associated workflow task
- `created_at`: Request timestamp
- `status`: pending/approved/denied
- `approved_by`: User who made decision
- `approved_at`: Decision timestamp
- `reason`: Decision rationale

Access complete history:
```bash
GET /api/approval/history?limit=1000
```

## Monitoring

### Check System Health
```bash
GET /api/approval/stats
```
Returns: pending count, approval/denial counts, history size, command classifications.

### List Pending Decisions
```bash
GET /api/approval/pending
```
Always shows what needs attention.

### Verify Command Classification
```bash
GET /api/approval/should-approve?command=<cmd>
```
Confirms whether a command is safe or dangerous in current mode.

## Production Deployment

### Recommended Configuration

1. **Default Mode**: `smart_approve`
   - Safe operations proceed automatically
   - Dangerous operations logged for review
   - Minimal friction for common tasks

2. **Notification Integration**: Subscribe to pending approvals
   - Send Slack/email notification when approval needed
   - Enable fast turnaround for high-priority workflows

3. **Audit Review**: Monitor approval history daily
   - Check for anomalies
   - Track which operations required approval
   - Identify patterns in automation

4. **Security Policy**:
   - Dangerous commands require approval from authorized users
   - Log all approval decisions
   - Review denied requests for security threats

## Testing

```bash
# 1. Create approval request
curl -X POST "http://localhost:8081/api/approval/request?command=execute_command&task_id=test"

# 2. Verify pending
curl http://localhost:8081/api/approval/pending

# 3. Approve it
APPROVAL_ID=$(curl -s http://localhost:8081/api/approval/pending | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['approvals'][0]['id'])")

curl -X POST "http://localhost:8081/api/approval/$APPROVAL_ID/approve?approved_by=test"

# 4. Check history
curl http://localhost:8081/api/approval/history

# 5. Verify stats updated
curl http://localhost:8081/api/approval/stats
```

## Troubleshooting

### Issue: All Commands Require Approval
**Check:**
```bash
GET /api/approval/mode
```
If mode is `approve_all` or `off`, change to `smart_approve`:
```bash
POST /api/approval/mode?mode=smart_approve
```

### Issue: Safe Commands Still Require Approval
**Check:**
```bash
GET /api/approval/should-approve?command=screenshot
```
If returns `requires_approval: true`, verify mode is `smart_approve` and command is in safe list.

### Issue: Approval History Growing Too Large
The system keeps last 1000 approvals. For archival:
```bash
GET /api/approval/history?limit=1000
# Export to CSV or database
```

## Integration with Coasty Desktop

In Coasty Desktop's chat interface:

```javascript
// Before executing an automation task
const approval = await fetch('http://localhost:8081/api/approval/request', {
  method: 'POST',
  body: JSON.stringify({
    command: userTask,
    task_id: workflowId
  })
});

// Wait for user approval in UI
// Show: "Approval #12345 required - approve/deny"
// Only execute after approval granted
```

## Next Steps

1. Integrate with workflow execution (already wired in approval_system.py)
2. Add approval request notifications (Slack/email)
3. Create approval dashboard UI
4. Set up audit log exports
5. Configure user roles (who can approve what)

---

**Status**: ✅ Fully Operational
**Endpoints**: 8 (all tested)
**Commands**: 27 classified (15 safe, 12 dangerous)
**Modes**: 4 (full_control, smart_approve, approve_all, off)
**Date**: 2026-06-08
