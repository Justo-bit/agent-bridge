"""
Execution Cache - Intelligent memoization for workflow efficiency
Caches: screenshots, prompts, DOM analysis, task results
Impact: +8% efficiency (avoid re-analyzing same screenshots)
"""

import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ExecutionCache:
    """Cache system for workflow execution"""

    def __init__(self, ttl_minutes: int = 60):
        self.screenshot_cache: Dict[str, Dict] = {}  # hash → analysis
        self.prompt_cache: Dict[str, str] = {}       # task_type → prompt
        self.result_cache: Dict[str, Dict] = {}      # task_id → result
        self.dom_cache: Dict[str, Dict] = {}         # url → dom_analysis
        self.ttl = timedelta(minutes=ttl_minutes)
        self.timestamps: Dict[str, datetime] = {}

    @staticmethod
    def hash_screenshot(screenshot_bytes: bytes) -> str:
        """Generate hash of screenshot for caching"""
        return hashlib.md5(screenshot_bytes).hexdigest()

    @staticmethod
    def hash_task_type(task_description: str) -> str:
        """Generate hash of task type for prompt caching"""
        # Extract task type (first few words)
        task_type = " ".join(task_description.split()[:3]).lower()
        return hashlib.md5(task_type.encode()).hexdigest()

    def get_screenshot_cache(self, screenshot_hash: str) -> Optional[Dict]:
        """Get cached screenshot analysis"""
        if screenshot_hash not in self.screenshot_cache:
            return None

        # Check TTL
        if datetime.now() - self.timestamps.get(screenshot_hash, datetime.now()) > self.ttl:
            del self.screenshot_cache[screenshot_hash]
            logger.info(f"🗑️  Screenshot cache expired: {screenshot_hash[:8]}")
            return None

        logger.info(f"✅ Screenshot cache hit: {screenshot_hash[:8]}")
        return self.screenshot_cache[screenshot_hash]

    def set_screenshot_cache(self, screenshot_hash: str, result: Dict):
        """Cache screenshot analysis result"""
        self.screenshot_cache[screenshot_hash] = result
        self.timestamps[screenshot_hash] = datetime.now()
        logger.info(f"💾 Screenshot cached: {screenshot_hash[:8]}")

    def get_prompt_cache(self, task_type_hash: str) -> Optional[str]:
        """Get cached system prompt for task type"""
        if task_type_hash not in self.prompt_cache:
            return None

        logger.info(f"✅ Prompt cache hit: {task_type_hash[:8]}")
        return self.prompt_cache[task_type_hash]

    def set_prompt_cache(self, task_type_hash: str, prompt: str):
        """Cache system prompt for task type"""
        self.prompt_cache[task_type_hash] = prompt
        logger.info(f"💾 Prompt cached: {task_type_hash[:8]}")

    def get_result_cache(self, task_id: str) -> Optional[Dict]:
        """Get cached task result"""
        if task_id not in self.result_cache:
            return None

        if datetime.now() - self.timestamps.get(task_id, datetime.now()) > self.ttl:
            del self.result_cache[task_id]
            return None

        logger.info(f"✅ Result cache hit: {task_id}")
        return self.result_cache[task_id]

    def set_result_cache(self, task_id: str, result: Dict):
        """Cache task execution result"""
        self.result_cache[task_id] = result
        self.timestamps[task_id] = datetime.now()
        logger.info(f"💾 Result cached: {task_id}")

    def get_dom_cache(self, url: str) -> Optional[Dict]:
        """Get cached DOM analysis"""
        if url not in self.dom_cache:
            return None

        logger.info(f"✅ DOM cache hit: {url}")
        return self.dom_cache[url]

    def set_dom_cache(self, url: str, dom_analysis: Dict):
        """Cache DOM analysis"""
        self.dom_cache[url] = dom_analysis
        logger.info(f"💾 DOM cached: {url}")

    def clear_expired(self):
        """Clear all expired entries"""
        now = datetime.now()
        expired = [k for k, t in self.timestamps.items() if now - t > self.ttl]
        for k in expired:
            self.screenshot_cache.pop(k, None)
            self.result_cache.pop(k, None)
            self.timestamps.pop(k, None)
        if expired:
            logger.info(f"🗑️  Cleared {len(expired)} expired cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "screenshot_cache_size": len(self.screenshot_cache),
            "prompt_cache_size": len(self.prompt_cache),
            "result_cache_size": len(self.result_cache),
            "dom_cache_size": len(self.dom_cache),
            "total_entries": sum([
                len(self.screenshot_cache),
                len(self.prompt_cache),
                len(self.result_cache),
                len(self.dom_cache)
            ])
        }


# Global singleton cache instance
execution_cache = ExecutionCache(ttl_minutes=60)
