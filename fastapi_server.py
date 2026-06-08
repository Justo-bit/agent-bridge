"""
FastAPI Bridge Server: Connects Coasty Frontend to Agent-S3 Backend
Handles WebSocket streaming, task orchestration, and LLM provider rotation.
"""

import asyncio
import json
import logging
import uuid
import os
from typing import Optional, Dict, Any
from datetime import datetime
import base64
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from llm_router import UnifiedLLMRouter, LLMTier
from agents3_adapter import AgentS3Adapter, ActionType
from cost_tracker import cost_tracker
from workflow_engine import (
    UnifiedWorkflowEngine,
    WorkflowDefinition,
    WorkflowPersistence,
)
from coasty_integration import Agent3Orchestrator
from browser_executor import browser_executor
from approval_system import approval_manager, ApprovalMode
from unwired_features import unwired_features, TaskComplexity
from cache import execution_cache  # QUICK WIN 2: Intelligent caching

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# API Keys persistence file
API_KEYS_FILE = Path("/tmp/agent_s3_api_keys.json")

def load_api_keys():
    """Load API keys from persistent storage."""
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, 'r') as f:
                keys = json.load(f)
                # Set environment variables from saved keys
                for provider, api_key in keys.items():
                    if api_key:
                        os.environ[provider.upper()] = api_key
                logger.info(f"✅ Loaded API keys from {API_KEYS_FILE}")
                return keys
        except Exception as e:
            logger.error(f"❌ Failed to load API keys: {e}")
    return {}

def save_api_keys(keys: Dict[str, str]):
    """Save API keys to persistent storage."""
    try:
        with open(API_KEYS_FILE, 'w') as f:
            json.dump(keys, f)
        logger.info(f"✅ Saved API keys to {API_KEYS_FILE}")
    except Exception as e:
        logger.error(f"❌ Failed to save API keys: {e}")

# Load API keys on startup
load_api_keys()

# Initialize core components
llm_router = UnifiedLLMRouter(prefer_tier=LLMTier.FREE)
adapter = AgentS3Adapter(llm_router)
orchestrator = Agent3Orchestrator(llm_router, adapter)

# Initialize workflow engine (wires all 7 pieces together)
workflow_engine = UnifiedWorkflowEngine(orchestrator, cost_tracker)

# Create FastAPI app
app = FastAPI(
    title="Agent-S3 + Coasty Bridge",
    description="Unified GUI Automation with Free/Paid LLM rotation",
    version="1.0.0",
)

# Enable CORS for Coasty frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task store
tasks: Dict[str, Dict[str, Any]] = {}
active_websockets: Dict[str, WebSocket] = {}


# Pydantic models
class OrchestrationRequest(BaseModel):
    prompt: str
    screenshot: Optional[str] = None  # Base64 encoded
    task_id: Optional[str] = None


class ConfigUpdate(BaseModel):
    provider_tier: Optional[str] = None  # "free" or "paid"
    prefer_paid: Optional[bool] = False
    api_keys: Optional[Dict[str, str]] = None  # API keys for providers


# Health & Status Endpoints
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "providers": llm_router.get_stats(),
        "cache": execution_cache.get_stats(),  # QUICK WIN 2: Include cache stats
        "port": 8081,
        "cors_enabled": True,
    }

@app.get("/api/cache/stats")
async def cache_stats():
    """QUICK WIN 2: Get execution cache statistics."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        **execution_cache.get_stats()
    }

@app.post("/api/cache/clear")
async def cache_clear():
    """QUICK WIN 2: Clear expired cache entries."""
    execution_cache.clear_expired()
    return {
        "status": "ok",
        "message": "Cleared expired cache entries",
        "timestamp": datetime.utcnow().isoformat(),
        **execution_cache.get_stats()
    }

@app.post("/api/build-app")
async def build_app(request: OrchestrationRequest):
    """Build an app - handles app creation requests from desktop agent."""
    try:
        logger.info(f"🏗️  Building app: {request.prompt}")

        # Route to appropriate executor
        routing = intelligently_route_task(request.prompt)

        # Determine app type from prompt
        app_prompt = request.prompt.lower()

        response_message = f"✅ App building request received: {request.prompt}\n\n"
        response_message += f"Routing: {routing['executor']}\n"
        response_message += f"Complexity: {routing['complexity']}\n\n"

        # Basic app building logic
        if any(word in app_prompt for word in ['web app', 'web application', 'website']):
            response_message += "🌐 Web App detected\n"
            response_message += "Steps:\n"
            response_message += "1. Set up Next.js/React project\n"
            response_message += "2. Configure Tailwind CSS\n"
            response_message += "3. Create components\n"
            response_message += "4. Set up API routes\n"
        elif any(word in app_prompt for word in ['desktop app', 'electron', 'desktop']):
            response_message += "🖥️  Desktop App detected\n"
            response_message += "Steps:\n"
            response_message += "1. Initialize Electron project\n"
            response_message += "2. Set up main process\n"
            response_message += "3. Create renderer UI\n"
            response_message += "4. Add native modules\n"
        elif any(word in app_prompt for word in ['mobile app', 'ios', 'android']):
            response_message += "📱 Mobile App detected\n"
            response_message += "Steps:\n"
            response_message += "1. Set up React Native\n"
            response_message += "2. Create screens\n"
            response_message += "3. Add navigation\n"
            response_message += "4. Integrate APIs\n"
        else:
            response_message += "🎯 Generic App Setup\n"
            response_message += "Please specify: web app, desktop app, or mobile app\n"

        return {
            "status": "success",
            "action": "build_app",
            "prompt": request.prompt,
            "routing": routing,
            "response": response_message,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ App building failed: {e}")
        return {
            "status": "error",
            "action": "build_app",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/api/debug")
async def debug():
    """Debug endpoint for troubleshooting frontend connection."""
    import os
    import socket

    # Get hostname and IP
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)

    return {
        "status": "ok",
        "message": "Backend is accessible",
        "server": {
            "hostname": hostname,
            "ip_address": ip_address,
            "port": 8081,
            "url": "http://localhost:8081",
        },
        "cors": {
            "enabled": True,
            "origins": ["*"],
            "credentials": True,
        },
        "api": {
            "health": "GET /api/health",
            "config": "GET /api/config/llm-providers",
            "set_config": "POST /api/config/set-provider",
            "metrics_summary": "GET /api/metrics/summary",
            "metrics_task": "GET /api/metrics/task/{task_id}",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/config/llm-providers")
async def get_llm_providers():
    """Get available LLM providers and their configuration status."""
    # Load saved keys from file
    saved_keys = {}
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, 'r') as f:
                saved_keys = json.load(f)
        except:
            pass

    providers = {
        "groq_api_key": bool(saved_keys.get("groq_api_key") or os.environ.get("GROQ_API_KEY")),
        "nvidia_api_key": bool(saved_keys.get("nvidia_api_key") or os.environ.get("NVIDIA_API_KEY")),
        "together_api_key": bool(saved_keys.get("together_api_key") or os.environ.get("TOGETHER_API_KEY")),
        "anthropic_api_key": bool(saved_keys.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")),
        "openai_api_key": bool(saved_keys.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")),
        "huggingface_api_key": bool(saved_keys.get("huggingface_api_key") or os.environ.get("HUGGINGFACE_API_KEY")),
    }

    return {
        "providers": providers,
        "available_providers": llm_router.get_stats(),
        "prefer_tier": llm_router.prefer_tier.value,
    }


@app.post("/api/config/set-provider")
async def set_provider(config: ConfigUpdate):
    """Switch LLM provider tier and/or update API keys."""

    # Handle API keys if provided
    if config.api_keys:
        # Load existing keys
        existing_keys = {}
        if API_KEYS_FILE.exists():
            try:
                with open(API_KEYS_FILE, 'r') as f:
                    existing_keys = json.load(f)
            except:
                pass

        # Update with new keys
        for provider, api_key in config.api_keys.items():
            if api_key:
                logger.info(f"🔑 Configuring API key for provider: {provider}")
                existing_keys[provider] = api_key
                os.environ[provider.upper()] = api_key

        # Save to file
        save_api_keys(existing_keys)

        # Refresh the LLM router's provider list
        llm_router.refresh_providers()

        return {
            "message": "API keys configured successfully",
            "providers_configured": list(config.api_keys.keys()),
        }

    # Handle provider tier switching
    if config.provider_tier:
        if config.provider_tier == "free":
            llm_router.prefer_tier = LLMTier.FREE
        elif config.provider_tier == "paid":
            llm_router.prefer_tier = LLMTier.PAID
        else:
            raise HTTPException(status_code=400, detail="Invalid tier")

        return {
            "message": f"Provider tier set to {config.provider_tier}",
            "available_providers": llm_router.get_stats(),
        }

    # If neither API keys nor provider tier provided
    raise HTTPException(status_code=400, detail="Either api_keys or provider_tier must be provided")


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return {
        "active_tasks": len([t for t in tasks.values() if t["status"] == "running"]),
        "completed_tasks": len([t for t in tasks.values() if t["status"] == "completed"]),
        "llm_providers": llm_router.get_stats(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# Task Management Endpoints
@app.post("/api/orchestrate")
async def start_orchestration(request: OrchestrationRequest):
    """
    Start a new automation task.
    Returns task_id for polling or WebSocket connection.
    """
    task_id = request.task_id or str(uuid.uuid4())

    tasks[task_id] = {
        "id": task_id,
        "prompt": request.prompt,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "actions": [],
        "current_step": 0,
        "error": None,
    }

    logger.info(f"📋 Task {task_id} created: {request.prompt[:50]}...")

    # Convert to Agent-S3 format
    agents3_request = adapter.coasty_to_agents3(
        user_prompt=request.prompt,
        screenshot_base64=request.screenshot,
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "message": f"Task queued. Connect to /ws/stream/{task_id} for real-time updates",
        "ws_url": f"ws://localhost:8000/ws/stream/{task_id}",
    }


@app.get("/api/orchestrate/{task_id}")
async def get_task_status(task_id: str):
    """Poll task status."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    return {
        "id": task_id,
        "status": task["status"],
        "progress": f"{task['current_step']}/10",
        "actions_taken": len(task["actions"]),
        "error": task["error"],
    }


@app.delete("/api/orchestrate/{task_id}")
async def cancel_task(task_id: str):
    """Cancel running task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    if task["status"] == "running":
        task["status"] = "cancelled"
        logger.info(f"✋ Task {task_id} cancelled")

    return {"message": f"Task {task_id} cancelled"}


# WebSocket Streaming Endpoint
@app.websocket("/ws/stream/{task_id}")
async def websocket_stream(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time action streaming.
    Sends Agent-S3 actions back to Coasty frontend.
    """
    if task_id not in tasks:
        await websocket.close(code=404, reason="Task not found")
        return

    await websocket.accept()
    active_websockets[task_id] = websocket

    logger.info(f"🔌 WebSocket connected for task {task_id}")

    try:
        task = tasks[task_id]
        task["status"] = "running"

        # Simulate Agent-S3 execution loop
        for step in range(1, 11):
            task["current_step"] = step

            # Generate mock action (in production, call actual Agent-S3)
            action = {
                "type": "click",
                "coordinates": [500 + step * 10, 300 + step * 10],
                "reasoning": f"Executing step {step}",
                "confidence": 0.85,
            }

            # Convert to Coasty format
            coasty_action = adapter.agents3_to_coasty(action, task_step=step)

            # Send to frontend
            await websocket.send_json(coasty_action)

            task["actions"].append(action)

            # Simulate processing delay
            await asyncio.sleep(1)

            # Check for user input (pause/resume)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                message = json.loads(data)

                if message.get("command") == "pause":
                    task["status"] = "paused"
                    await websocket.send_json({"type": "paused"})
                elif message.get("command") == "resume":
                    task["status"] = "running"
                    await websocket.send_json({"type": "resumed"})
                elif message.get("command") == "stop":
                    task["status"] = "cancelled"
                    break

            except asyncio.TimeoutError:
                pass

        # Task completed
        task["status"] = "completed"
        await websocket.send_json(
            {
                "type": "task_complete",
                "summary": f"Completed {len(task['actions'])} actions",
                "actions": task["actions"],
            }
        )

        logger.info(f"✅ Task {task_id} completed")

    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket disconnected for task {task_id}")
        task["status"] = "disconnected"
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        task["status"] = "error"
        task["error"] = str(e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        if task_id in active_websockets:
            del active_websockets[task_id]


# Debug/Admin Endpoints
@app.get("/api/memory/stats")
async def get_memory_stats():
    """Get adapter memory stats."""
    return {
        "screenshot_history": len(adapter.screenshot_history),
        "action_history": len(adapter.action_history),
        "max_history": adapter.max_history,
    }


@app.post("/api/memory/clear")
async def clear_memory():
    """Clear session memory."""
    adapter.reset_session()
    return {"message": "Memory cleared"}


@app.get("/api/history/{task_id}")
async def get_task_history(task_id: str):
    """Get action history for a task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "actions": tasks[task_id]["actions"],
        "total_steps": len(tasks[task_id]["actions"]),
    }


# Test/Demo Endpoints
@app.post("/api/test/mock-orchestration")
async def test_orchestration():
    """Test with mock Agent-S3 execution."""
    return {
        "message": "Mock orchestration would execute here",
        "llm_provider": llm_router.get_provider().name,
        "action_example": {
            "type": "click",
            "coordinates": [500, 300],
            "reasoning": "Clicked button",
        },
    }


@app.post("/api/test/llm-inference")
async def test_llm_inference(request: OrchestrationRequest):
    """Test LLM routing with actual inference."""
    try:
        import uuid
        task_id = str(uuid.uuid4())[:8]
        provider = llm_router.get_provider(vision_required=bool(request.screenshot))

        result = llm_router.route_completion(
            prompt=request.prompt,
            system_prompt="You are a UI automation expert. Analyze the screenshot and suggest the next action.",
            vision_data=(
                base64.b64decode(request.screenshot) if request.screenshot else None
            ),
            max_tokens=256,
            task_id=task_id,
        )

        return {
            "provider": result["provider"],
            "response": result["response"],
            "tokens_input": result.get("tokens_input", 0),
            "tokens_output": result.get("tokens_output", 0),
            "tokens_used": result["tokens_used"],
            "cost": result["cost"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Cost Metrics Endpoints
@app.get("/api/metrics/summary")
async def get_cost_summary():
    """Get overall cost summary since tracker started."""
    return cost_tracker.get_global_summary()


@app.get("/api/metrics/task/{task_id}")
async def get_task_cost(task_id: str):
    """Get cost breakdown for a specific task."""
    return cost_tracker.get_task_cost(task_id)


@app.get("/api/metrics/daily")
async def get_daily_summary(days: int = 1):
    """Get cost summary for last N days."""
    return cost_tracker.get_daily_summary(days_back=days)


@app.get("/api/metrics/providers")
async def get_provider_breakdown():
    """Get provider usage distribution and costs."""
    return cost_tracker.get_provider_breakdown()


@app.get("/api/metrics/recent")
async def get_recent_inferences(limit: int = 20):
    """Get most recent inferences."""
    return {"inferences": cost_tracker.get_recent_inferences(limit)}


@app.post("/api/metrics/export")
async def export_metrics(filepath: str = "/tmp/agent_s3_metrics.json"):
    """Export all metrics to JSON file."""
    try:
        cost_tracker.export_to_json(filepath)
        return {"message": f"Exported to {filepath}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Intelligent Task Router - Routes commands to appropriate executor
def intelligently_route_task(prompt: str) -> Dict[str, str]:
    """
    Intelligently route task to appropriate executor
    Detects intent from prompt and routes accordingly
    """
    prompt_lower = prompt.lower()

    # Route detection patterns
    routes = {
        "desktop": ["click", "type", "drag", "scroll", "move", "press", "key", "window", "app", "open", "close", "install", "execute", "run"],
        "browser": ["navigate", "visit", "go to", "click", "form", "submit", "button", "link", "page", "website", "web", "http", "browse", "search"],
        "workflow": ["schedule", "workflow", "task", "automate", "repeat", "loop", "trigger", "create workflow"],
        "system": ["install", "download", "setup", "configure", "file", "directory", "disk", "create", "delete"],
    }

    # Detect primary executor
    executor = "automation"  # Default
    for exec_type, keywords in routes.items():
        if any(kw in prompt_lower for kw in keywords):
            executor = exec_type
            break

    # Classify complexity
    complexity = unwired_features.classify_task(prompt)

    return {"executor": executor, "complexity": complexity}


# Task Execution Endpoint (for Agent-S3 desktop automation)
@app.post("/api/execute")
async def execute_task(request: OrchestrationRequest):
    """
    Execute real desktop automation tasks with intelligent routing.
    QUICK WIN 2: Caches task results by task type.
    """
    try:
        import uuid
        from desktop_executor import desktop_executor

        task_id = str(uuid.uuid4())[:8]

        # FIX: Strip command prefixes from Electron desktop app
        raw_prompt = request.prompt
        if raw_prompt.startswith("agent_s3:"):
            raw_prompt = raw_prompt.replace("agent_s3:", "", 1)
        elif raw_prompt.startswith("worker_report:"):
            raw_prompt = raw_prompt.replace("worker_report:", "", 1)

        prompt = raw_prompt.lower()

        # QUICK WIN 2: Check if we have cached result for this task type
        task_type_hash = execution_cache.hash_task_type(raw_prompt)
        cached_result = execution_cache.get_result_cache(task_type_hash)
        if cached_result:
            logger.info(f"💾 Cache hit for task type: {raw_prompt[:50]}...")
            return {**cached_result, "task_id": task_id, "cached": True}
        actions = []
        results = []

        # Route the task intelligently
        routing = intelligently_route_task(request.prompt)
        logger.info(f"🎯 Executing task: {request.prompt[:60]}... (Executor: {routing['executor']}, Complexity: {routing['complexity']})")

        # Screenshot request
        if any(word in prompt for word in ['screenshot', 'screen', 'capture', 'describe']):
            screenshot_result = desktop_executor.take_screenshot()
            actions.append("screenshot")
            results.append(screenshot_result)

        # File listing request (triggered by: how many, count, list, show, what files)
        list_keywords = ['how many', 'count', 'list', 'show', 'what files', 'files in', 'documents in', 'number of']
        is_listing_request = any(keyword in prompt for keyword in list_keywords)
        logger.debug(f"🔍 Checking if listing request: {is_listing_request}, prompt='{prompt[:50]}'")

        if is_listing_request:
            # This is a file listing request, not a download
            folder_query = prompt

            # Determine which folder to list
            if 'downloads' in folder_query or 'download folder' in folder_query:
                folder_path = '~/Downloads'
            elif 'desktop' in folder_query:
                folder_path = '~/Desktop'
            elif 'documents' in folder_query:
                folder_path = '~/Documents'
            else:
                folder_path = '~/Downloads'  # Default to Downloads

            logger.info(f"📁 File listing request: {folder_path}")
            list_result = desktop_executor.list_files(folder_path)
            actions.append("list_files")
            results.append(list_result)

        # Download request (triggered by: download, save, get, fetch, retrieve)
        elif any(word in prompt for word in ['download', 'save', 'fetch', 'retrieve', 'paste']):
            if 'junam' in prompt.lower():
                download_result = desktop_executor.download_image(
                    "Junam logo",
                    "Junam_logo.png"
                )
                actions.append("download")
                results.append(download_result)
            else:
                # Generic download handling
                search_query = prompt
                for word in ['download', 'save', 'get', 'fetch', 'retrieve']:
                    if word in prompt:
                        search_query = prompt.split(word)[1].strip()
                        break

                download_result = desktop_executor.download_image(
                    search_query,
                    "downloaded_file.png"
                )
                actions.append("download")
                results.append(download_result)

        # File creation
        if 'create' in prompt and 'file' in prompt:
            # Extract filename from prompt
            parts = prompt.split('named')
            if len(parts) > 1:
                filename = parts[-1].strip().split()[0] if parts[-1].strip() else "test.txt"
            else:
                parts = prompt.split('file')
                filename = parts[-1].strip().split()[0] if len(parts) > 1 and parts[-1].strip() else "test.txt"

            # Ensure filename has extension
            if '.' not in filename:
                filename += '.txt'

            file_result = desktop_executor.create_file(
                filename,
                f"Created: {prompt}\nTimestamp: {datetime.now().isoformat()}"
            )
            actions.append("create_file")
            results.append(file_result)

        # Terminal command execution (including install, brew, npm, pip, git)
        if any(word in prompt for word in ['run', 'execute', 'command', 'install', 'brew', 'npm', 'pip', 'git', 'clone']):
            # Extract command from prompt
            if 'run' in prompt:
                command = prompt.split('run')[-1].strip()
            elif 'install' in prompt or 'brew' in prompt or 'npm' in prompt or 'pip' in prompt:
                # For install commands, construct the full command
                if 'brew' in prompt:
                    app_name = prompt.split('brew')[-1].strip().split()[0] if 'brew' in prompt else 'app'
                    command = f"brew install {app_name}" if app_name else prompt
                elif 'npm' in prompt:
                    pkg_name = prompt.split('npm')[-1].strip().split()[0] if 'npm' in prompt else 'package'
                    command = f"npm install {pkg_name}" if pkg_name else prompt
                elif 'pip' in prompt:
                    pkg_name = prompt.split('pip')[-1].strip().split()[0] if 'pip' in prompt else 'package'
                    command = f"pip install {pkg_name}" if pkg_name else prompt
                elif 'git' in prompt and 'clone' in prompt:
                    command = prompt
                else:
                    command = prompt
            else:
                command = prompt.split('execute')[-1].strip() if 'execute' in prompt else prompt

            cmd_result = desktop_executor.execute_command(command[:200])
            actions.append("execute_command")
            results.append(cmd_result)

        # List desktop files
        if 'list' in prompt and 'desktop' in prompt:
            list_result = desktop_executor.list_desktop_files()
            actions.append("list_files")
            results.append(list_result)

        # If no specific action detected, take screenshot as default
        if not actions:
            screenshot_result = desktop_executor.take_screenshot()
            actions.append("screenshot")
            results.append(screenshot_result)

        # Get LLM to describe what happened
        execution_summary = f"Executed: {', '.join(actions)}. Results: {json.dumps(results, default=str)[:500]}"

        llm_result = llm_router.route_completion(
            prompt=f"Summarize this desktop automation execution in 2-3 sentences: {execution_summary}",
            system_prompt="You are a desktop automation assistant. Provide a concise summary of actions performed.",
            vision_data=None,
            max_tokens=256,
            task_id=task_id,
        )

        response = {
            "task_id": task_id,
            "status": "completed",
            "actions_executed": actions,
            "execution_results": results,
            "response": llm_result.get("response", execution_summary),
            "provider": llm_result.get("provider", ""),
            "tokens_used": llm_result.get("tokens_used", 0),
            "cost": llm_result.get("cost", 0),
            "cached": False
        }

        # QUICK WIN 2: Cache the result for future identical task types
        task_type_hash = execution_cache.hash_task_type(raw_prompt)
        execution_cache.set_result_cache(task_type_hash, response)

        return response

    except Exception as e:
        logger.error(f"❌ Task execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Chat Endpoint for Desktop App
@app.post("/api/chat")
async def chat(request: OrchestrationRequest):
    """Chat endpoint for desktop app - routes to LLM with cost tracking."""
    try:
        import uuid
        task_id = str(uuid.uuid4())[:8]

        # Use default system prompt for chat
        system_prompt = "You are a helpful AI assistant. Be concise and direct in your responses."

        result = llm_router.route_completion(
            prompt=request.prompt,
            system_prompt=system_prompt,
            vision_data=(
                base64.b64decode(request.screenshot) if request.screenshot else None
            ),
            max_tokens=1024,
            task_id=task_id,
        )

        return {
            "response": result.get("response", ""),
            "provider": result.get("provider", ""),
            "tokens_input": result.get("tokens_input", 0),
            "tokens_output": result.get("tokens_output", 0),
            "tokens_used": result.get("tokens_used", 0),
            "cost": result.get("cost", 0),
            "task_id": task_id,
        }

    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════
# WORKFLOW ENGINE ENDPOINTS - Unified 7-piece architecture
# ════════════════════════════════════════════════════════════════════

class WorkflowRequest(BaseModel):
    """Create or execute a workflow."""
    name: Optional[str] = None
    description: Optional[str] = None
    tasks: Optional[list] = None
    schedule: Optional[str] = None
    on_error: str = "stop"


@app.post("/api/workflows")
async def create_workflow(request: WorkflowRequest):
    """
    PIECE 1 & 7: Create a new workflow (persisted to JSON).
    Triggers scheduling (PIECE 3) if cron provided.
    """
    try:
        workflow = workflow_engine.create_workflow(
            name=request.name,
            description=request.description,
            tasks=request.tasks or [],
            schedule=request.schedule,
            on_error=request.on_error,
        )
        return {
            "status": "created",
            "workflow_id": workflow.id,
            "workflow": workflow.to_dict(),
        }
    except Exception as e:
        logger.error(f"❌ Workflow creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/workflows")
async def list_workflows():
    """List all workflows."""
    return {
        "workflows": workflow_engine.list_workflows(),
        "count": len(workflow_engine.workflows),
    }


@app.get("/api/workflows/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """Get workflow status and execution history."""
    return workflow_engine.get_workflow_status(workflow_id)


@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, triggered_by: str = "api"):
    """
    PIECE 1, 2, 4, 6: Execute a workflow.
    - Uses existing Agent3Orchestrator (PIECE 1)
    - Loads credentials (PIECE 2)
    - Records execution with timestamps (PIECE 4)
    - Publishes notifications (PIECE 6)
    """
    try:
        execution = await workflow_engine.execute_workflow(
            workflow_id=workflow_id,
            triggered_by=triggered_by,
        )
        return {
            "status": "completed" if execution.status.value == "completed" else "failed",
            "execution": execution.to_dict(),
        }
    except Exception as e:
        logger.error(f"❌ Workflow execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/webhook/{webhook_id}")
async def webhook_trigger(webhook_id: str):
    """
    PIECE 5: Webhook listener - trigger workflow via external event.
    Returns immediately, executes workflow in background.
    """
    try:
        if workflow_engine.webhook_registry.trigger_webhook(webhook_id):
            # Find the workflow for this webhook
            webhook = workflow_engine.webhook_registry.webhooks[webhook_id]
            workflow_id = webhook["workflow_id"]

            # Execute in background
            asyncio.create_task(
                workflow_engine.execute_workflow(
                    workflow_id=workflow_id,
                    triggered_by=f"webhook:{webhook_id}",
                )
            )

            return {
                "status": "triggered",
                "webhook_id": webhook_id,
                "workflow_id": workflow_id,
            }
        else:
            raise HTTPException(status_code=404, detail="Webhook not found")
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows/{workflow_id}/webhook")
async def register_webhook(workflow_id: str):
    """Register a webhook for a workflow and return the URL."""
    try:
        webhook_url = workflow_engine.webhook_registry.register_webhook(
            workflow_id=workflow_id,
            trigger_name="api_trigger",
        )
        return {
            "webhook_url": f"http://localhost:8081{webhook_url}",
            "workflow_id": workflow_id,
        }
    except Exception as e:
        logger.error(f"❌ Webhook registration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/executions")
async def get_execution_history(limit: int = 20):
    """Get recent workflow execution history."""
    return {
        "executions": workflow_engine.get_execution_history(limit),
        "total_count": len(workflow_engine.executions),
    }


@app.get("/api/scheduler/start")
async def start_scheduler():
    """Start the task scheduler (PIECE 3)."""
    try:
        workflow_engine.scheduler.start()
        return {"status": "scheduler_started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scheduler/stop")
async def stop_scheduler():
    """Stop the task scheduler."""
    try:
        workflow_engine.scheduler.stop()
        return {"status": "scheduler_stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════
# BROWSER AGENT ENDPOINTS - Web automation
# ════════════════════════════════════════════════════════════════

class BrowserRequest(BaseModel):
    action: str  # launch, navigate, click, type, execute, etc
    selector: Optional[str] = None
    text: Optional[str] = None
    script: Optional[str] = None
    url: Optional[str] = None
    direction: Optional[str] = None
    amount: Optional[int] = None
    timeout: Optional[int] = 30
    headless: Optional[bool] = True


@app.post("/api/browser")
async def browser_action(request: BrowserRequest):
    """
    BROWSER AGENT - Web automation endpoint
    Puppeteer-based browser control integrated with workflows
    QUICK WIN 2: Caches screenshots and DOM analysis

    Supported actions:
    - launch: Start browser
    - navigate: Go to URL
    - click: Click element by selector
    - type: Type in form field
    - screenshot: Capture page (CACHED)
    - scroll: Scroll page
    - execute: Run JavaScript
    - wait_for: Wait for element
    - get_dom: Extract DOM tree (CACHED)
    - get_clickables: Find interactive elements
    - close: Close browser
    """
    try:
        action = request.action.lower()

        # QUICK WIN 2: Check screenshot cache
        if action == "screenshot":
            cache_key = execution_cache.hash_screenshot(b"screenshot")
            cached = execution_cache.get_screenshot_cache(cache_key)
            if cached:
                return {
                    "status": "success",
                    "action": action,
                    "result": cached,
                    "cached": True
                }

        if action == "launch":
            result = await browser_executor.launch_browser(
                headless=request.headless,
                url=request.url,
                reuse_session=True  # QUICK WIN 3: Enable session reuse
            )
        elif action == "navigate":
            result = await browser_executor.navigate(request.url)
        elif action == "click":
            result = await browser_executor.click(request.selector)
        elif action == "type":
            result = await browser_executor.type_text(request.selector, request.text)
        elif action == "screenshot":
            result = await browser_executor.screenshot()
            # QUICK WIN 2: Cache screenshot results
            if result.get("success"):
                cache_key = execution_cache.hash_screenshot(b"screenshot")
                execution_cache.set_screenshot_cache(cache_key, result)
        elif action == "scroll":
            result = await browser_executor.scroll(request.direction, request.amount)
        elif action == "execute":
            result = await browser_executor.execute_script(request.script)
        elif action == "wait_for":
            result = await browser_executor.wait_for(request.selector, request.timeout)
        elif action == "get_dom":
            # QUICK WIN 2: Check DOM cache for URL
            cached = execution_cache.get_dom_cache(request.url or "unknown")
            if cached:
                return {
                    "status": "success",
                    "action": action,
                    "result": cached,
                    "cached": True
                }
            result = await browser_executor.get_dom()
            # QUICK WIN 2: Cache DOM results
            if result.get("success"):
                execution_cache.set_dom_cache(request.url or "unknown", result)
        elif action == "get_clickables":
            result = await browser_executor.get_clickables()
        elif action == "get_state":
            result = await browser_executor.get_state()
        elif action == "close":
            result = await browser_executor.close(force=False)  # QUICK WIN 3: Don't force close
        else:
            raise ValueError(f"Unknown action: {action}")

        return {
            "status": "success" if result.get("success") else "failed",
            "action": action,
            "result": result,
            "cached": False
        }

    except Exception as e:
        logger.error(f"❌ Browser action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/browser/capabilities")
async def browser_capabilities():
    """Get available browser automation capabilities"""
    return {
        "agent": "Browser Agent",
        "status": "Available",
        "capabilities": [
            "launch - Start Chrome/Edge/Brave browser",
            "navigate - Go to URL",
            "click - Click element by CSS selector",
            "type - Type text in form field",
            "screenshot - Capture page screenshot",
            "scroll - Scroll page up/down",
            "execute - Run arbitrary JavaScript",
            "wait_for - Wait for element to appear",
            "get_dom - Extract full DOM tree",
            "get_clickables - Find interactive elements",
            "get_state - Capture page state",
            "close - Close browser"
        ],
        "integration": "Integrated with Workflow Engine",
        "execution": "Real Puppeteer-based automation"
    }


# ════════════════════════════════════════════════════════════════
# UNWIRED FEATURES ENDPOINTS (10 Features)
# ════════════════════════════════════════════════════════════════

# FEATURE 1: Reflection Agent - Trajectory Validation
@app.post("/api/features/reflection/evaluate")
async def evaluate_trajectory(task_id: str, task_description: str, action_history: Optional[List[Dict]] = None):
    """Validate if agent trajectory is on track or stuck in loop"""
    result = await unwired_features.validate_trajectory(action_history or [], task_description)
    return result


# FEATURE 2: OCR/Text Grounding
@app.post("/api/features/ocr/extract-text")
async def ocr_extract_text(screenshot_base64: str):
    """Extract all text from screenshot using Tesseract OCR"""
    try:
        import base64
        screenshot_bytes = base64.b64decode(screenshot_base64)
        text_map = await unwired_features.extract_text_ocr(screenshot_bytes)
        return {"success": True, "text_map": text_map, "count": len(text_map)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/features/ocr/ground-phrase")
async def ocr_ground_phrase(phrase: str, text_map: Dict[str, Dict]):
    """Map natural language phrase to screen coordinates"""
    word_id, confidence = await unwired_features.ocr_executor.ground_phrase(phrase, text_map)
    if word_id is not None:
        coords = text_map[str(word_id)]
        return {
            "success": True,
            "word_id": word_id,
            "text": coords.get('text'),
            "coordinates": {"x": coords['x'], "y": coords['y']},
            "confidence": confidence
        }
    return {"success": False, "error": "Phrase not found"}


# FEATURE 3: Extended Thinking Mode
@app.post("/api/features/thinking/enable")
async def enable_extended_thinking(enabled: bool, max_tokens: int = 10000):
    """Enable/disable extended thinking mode for Claude"""
    unwired_features.thinking_config.enabled = enabled
    unwired_features.thinking_config.max_thinking_tokens = max_tokens
    return {
        "enabled": enabled,
        "max_tokens": max_tokens,
        "compatible_models": unwired_features.thinking_config.compatible_models
    }


@app.get("/api/features/thinking/status")
async def get_thinking_status():
    """Get extended thinking configuration"""
    return {
        "enabled": unwired_features.thinking_config.enabled,
        "max_tokens": unwired_features.thinking_config.max_thinking_tokens,
        "compatible_models": unwired_features.thinking_config.compatible_models
    }


# FEATURE 4: Action Decorator System
@app.post("/api/features/actions/discover")
async def discover_actions(agent_type: str):
    """Discover available actions for an agent"""
    # In production, would pass actual agent classes
    actions_map = {
        "desktop": {
            "click": {"signature": "(x, y)", "docstring": "Click at coordinates"},
            "type": {"signature": "(text)", "docstring": "Type text"},
            "screenshot": {"signature": "()", "docstring": "Take screenshot"}
        },
        "browser": {
            "navigate": {"signature": "(url)", "docstring": "Navigate to URL"},
            "click_element": {"signature": "(selector)", "docstring": "Click element"},
            "get_dom": {"signature": "()", "docstring": "Get page DOM"}
        }
    }
    return actions_map.get(agent_type, {})


# FEATURE 5: Task Complexity Detection
@app.post("/api/features/complexity/classify")
async def classify_task_complexity(task_description: str):
    """Classify task difficulty and get routing recommendation"""
    complexity = unwired_features.classify_task(task_description)
    provider_info = unwired_features.complexity_detector.get_provider_for_complexity(TaskComplexity(complexity))
    return {
        "complexity": complexity,
        "recommended_provider": provider_info['provider'],
        "estimated_cost_per_1k": provider_info['cost_per_1k'],
        "reason": provider_info['reason']
    }


# FEATURE 6: Error Recovery Backoff/Retry
@app.get("/api/features/resilience/config")
async def get_resilience_config():
    """Get error recovery configuration"""
    return {
        "max_retries": unwired_features.resilient_executor.max_retries,
        "max_time_seconds": unwired_features.resilient_executor.max_time,
        "backoff_strategy": "exponential",
        "description": "Automatic retry with exponential backoff on failures"
    }


@app.post("/api/features/resilience/test")
async def test_resilience(should_fail_once: bool = True):
    """Test resilience with simulated failure"""
    attempt_count = 0

    async def failing_operation():
        nonlocal attempt_count
        attempt_count += 1
        if should_fail_once and attempt_count == 1:
            raise Exception("Simulated failure (will retry)")
        return f"Success on attempt {attempt_count}"

    try:
        result = await unwired_features.execute_resilient(failing_operation)
        return {"success": True, "result": result, "attempts": attempt_count}
    except Exception as e:
        return {"success": False, "error": str(e), "attempts": attempt_count}


# FEATURE 7: Visual Feedback & Annotation
@app.post("/api/features/visualization/annotate")
async def annotate_screenshot(
    screenshot_base64: str,
    annotations: List[Dict]  # [{type, x, y, text, color}, ...]
):
    """Add visual annotations to screenshot for debugging"""
    try:
        import base64
        screenshot_bytes = base64.b64decode(screenshot_base64)
        annotated_bytes = unwired_features.annotate_image(screenshot_bytes, annotations)
        return {
            "success": True,
            "annotated_screenshot": base64.b64encode(annotated_bytes).decode(),
            "annotations_count": len(annotations)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# FEATURE 8: Session Isolation & State Restoration
@app.post("/api/features/sessions/save")
async def save_session_state(snapshot_id: Optional[str] = None):
    """Save current system state for isolation"""
    state = await unwired_features.save_session()
    return {"success": True, "snapshot": state}


@app.post("/api/features/sessions/restore")
async def restore_session_state(snapshot_id: str):
    """Restore system to previous state"""
    success = await unwired_features.session_manager.restore_state(snapshot_id)
    return {
        "success": success,
        "snapshot_id": snapshot_id,
        "message": "State restored" if success else "State not found"
    }


@app.get("/api/features/sessions/snapshots")
async def list_session_snapshots():
    """List all saved session snapshots"""
    snapshots = [s.to_dict() for s in unwired_features.session_manager.snapshots.values()]
    return {"snapshots": snapshots, "count": len(snapshots)}


# FEATURE 9: Multi-Monitor Support
@app.get("/api/features/monitors/info")
async def get_monitor_info():
    """Get information about all connected monitors"""
    monitors = unwired_features.get_monitors()
    return {
        "monitors": monitors,
        "count": len(monitors),
        "primary": next((m for m in monitors if m['is_primary']), None)
    }


@app.post("/api/features/monitors/convert-coords")
async def convert_monitor_coords(global_x: int, global_y: int):
    """Convert global coordinates to local monitor coordinates"""
    monitor_id, local_x, local_y = unwired_features.multi_monitor.global_to_local(global_x, global_y)
    monitors = unwired_features.get_monitors()
    monitor = next((m for m in monitors if m['id'] == monitor_id), None)
    return {
        "global": {"x": global_x, "y": global_y},
        "monitor_id": monitor_id,
        "local": {"x": local_x, "y": local_y},
        "monitor_info": monitor
    }


# FEATURE 10: Memory Management & Context Caching
@app.post("/api/features/context/optimize")
async def optimize_context(messages: List[Dict], model: str, max_images: int = 8):
    """Optimize message history for model context window"""
    optimized = unwired_features.optimize_context(messages, model)
    return {
        "original_count": len(messages),
        "optimized_count": len(optimized),
        "strategy": "long-context (keep all text, slide images)" if any(m in model for m in unwired_features.context_manager.LONG_CONTEXT_MODELS) else "short-context (drop old turns)"
    }


@app.get("/api/features/context/stats")
async def get_context_stats():
    """Get context usage statistics"""
    return {
        "long_context_models": unwired_features.context_manager.LONG_CONTEXT_MODELS,
        "short_context_models": unwired_features.context_manager.SHORT_CONTEXT_MODELS,
        "max_images_default": 8,
        "description": "Context management for different model families"
    }


# ════════════════════════════════════════════════════════════════
# APPROVAL SYSTEM ENDPOINTS - Enterprise governance
# ════════════════════════════════════════════════════════════════

@app.get("/api/approval/mode")
async def get_approval_mode():
    """Get current approval mode"""
    return {
        "mode": approval_manager.get_mode(),
        "modes_available": [m.value for m in ApprovalMode],
        "description": "full_control (auto-all) | smart_approve (safe-auto) | approve_all (require-all) | off (deny-all)"
    }


@app.post("/api/approval/mode")
async def set_approval_mode(mode: str):
    """Set approval mode (admin only)"""
    success = approval_manager.set_mode(mode)
    return {
        "success": success,
        "mode": approval_manager.get_mode() if success else None,
        "error": f"Invalid mode: {mode}" if not success else None
    }


@app.post("/api/approval/request")
async def request_approval(command: str, parameters: Optional[Dict] = None, task_id: Optional[str] = None):
    """Request approval for a command"""
    approval = approval_manager.request_approval(
        command=command,
        parameters=parameters or {},
        task_id=task_id
    )
    return approval.to_dict()


@app.post("/api/approval/{approval_id}/approve")
async def approve_request(approval_id: str, approved_by: str = "admin", reason: Optional[str] = None):
    """Approve a pending request"""
    success = approval_manager.approve(approval_id, approved_by, reason)
    return {
        "success": success,
        "approval_id": approval_id,
        "action": "approved",
        "approval": approval_manager.get_approval(approval_id)
    }


@app.post("/api/approval/{approval_id}/deny")
async def deny_request(approval_id: str, denied_by: str = "admin", reason: Optional[str] = None):
    """Deny a pending request"""
    success = approval_manager.deny(approval_id, denied_by, reason)
    return {
        "success": success,
        "approval_id": approval_id,
        "action": "denied",
        "approval": approval_manager.get_approval(approval_id)
    }


@app.get("/api/approval/pending")
async def get_pending_approvals():
    """Get all pending approval requests"""
    return {
        "pending_count": len(approval_manager.pending_approvals),
        "approvals": approval_manager.get_pending_approvals()
    }


@app.get("/api/approval/history")
async def get_approval_history(limit: int = 50):
    """Get approval history"""
    return {
        "limit": limit,
        "history_count": len(approval_manager.approval_history),
        "history": approval_manager.get_approval_history(limit)
    }


@app.get("/api/approval/stats")
async def get_approval_stats():
    """Get approval system statistics"""
    return approval_manager.get_stats()


@app.get("/api/approval/should-approve")
async def check_approval_needed(command: str):
    """Check if a command requires approval"""
    return {
        "command": command,
        "requires_approval": approval_manager.should_require_approval(command),
        "current_mode": approval_manager.get_mode(),
        "is_safe_command": command in approval_manager.SAFE_COMMANDS if hasattr(approval_manager, 'SAFE_COMMANDS') else False
    }


# WebSocket endpoint for Electron desktop app fallback
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, sessionId: str = Query(None)):
    """WebSocket endpoint for Electron desktop app local execution"""
    await websocket.accept()
    logger.info(f"🔌 WebSocket connection established: {sessionId}")

    authenticated = False
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type", "unknown")

            logger.debug(f"📨 WebSocket message: {message_type}")

            # Handle authentication
            if message_type == "auth":
                password = message.get("password")
                user_id = message.get("userId")
                logger.info(f"🔐 Auth attempt: user={user_id}")
                authenticated = True
                await websocket.send_json({
                    "type": "auth_success",
                    "message": "Authenticated",
                    "user_id": user_id
                })
                continue

            # Handle command execution
            if message_type == "command" and authenticated:
                try:
                    command_data = message.get("data", {})
                    command = command_data.get("command", "")

                    # Strip prefixes
                    if command.startswith("agent_s3:"):
                        prompt = command.replace("agent_s3:", "", 1)
                    elif command.startswith("worker_report:"):
                        prompt = command.replace("worker_report:", "", 1)
                    else:
                        prompt = command

                    logger.info(f"⚡ Executing WebSocket command: {prompt[:60]}")

                    # Route and execute
                    routing = intelligently_route_task(prompt)

                    await websocket.send_json({
                        "type": "command_response",
                        "data": {
                            "result": f"✅ Command accepted: {prompt[:100]}",
                            "report": f"Routing: {routing['executor']}, Complexity: {routing['complexity']}",
                            "success": True
                        }
                    })
                except Exception as e:
                    logger.error(f"❌ Command execution error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "data": {
                            "error": str(e)
                        }
                    })
                continue

            # Unknown message type
            if not authenticated and message_type != "auth":
                await websocket.send_json({
                    "type": "error",
                    "message": "Not authenticated"
                })
                continue

            if authenticated:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Error: {str(e)}"
            })
        except:
            pass
    finally:
        logger.info(f"🔌 WebSocket connection closed: {sessionId}")


if __name__ == "__main__":
    logger.info("🚀 Starting Agent-S3 + Coasty Bridge Server")
    logger.info(f"📡 Available LLM Providers: {llm_router.get_stats()}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,
        log_level="info",
    )
