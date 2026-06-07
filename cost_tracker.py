"""
Cost Tracking & Metrics System for Agent-S3 + Coasty
Tracks token usage and costs across all LLM providers.
Measures actual savings vs baseline (GPT-4o only).
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class TokenPricing:
    """Pricing per million tokens for each provider."""
    provider_name: str
    input_cost_per_m: float  # $ per million input tokens
    output_cost_per_m: float  # $ per million output tokens


# Official pricing as of 2024
PROVIDER_PRICING = {
    "Groq (Llama 3.3 70B)": TokenPricing("Groq", 0.0, 0.0),
    "HuggingFace Inference": TokenPricing("HuggingFace", 0.0, 0.0),
    "OpenAI GPT-4V": TokenPricing("OpenAI GPT-4V", 10.0, 30.0),
    "Anthropic Claude 3.5": TokenPricing("Anthropic", 3.0, 15.0),
    "Together AI": TokenPricing("Together AI", 0.5, 1.5),
}

# Baseline for comparison: GPT-4o (most commonly used)
BASELINE_PRICING = TokenPricing("OpenAI GPT-4o", 5.0, 15.0)


@dataclass
class InferenceRecord:
    """Record of a single LLM inference."""
    task_id: str
    provider: str
    tokens_input: int
    tokens_output: int
    total_tokens: int
    timestamp: str
    cost: float
    model: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CostTracker:
    """
    Tracks token usage and costs across all tasks.
    Thread-safe for concurrent task execution.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.inferences: List[InferenceRecord] = []  # All inferences
        self.task_costs: Dict[str, List[InferenceRecord]] = defaultdict(list)  # Per task
        self.provider_usage = defaultdict(int)  # Provider call count

        logger.info("✅ Cost Tracker initialized")

    def record_inference(
        self,
        task_id: str,
        provider: str,
        tokens_input: int,
        tokens_output: int,
        model: str,
    ) -> float:
        """
        Record a single LLM inference.

        Args:
            task_id: Unique task identifier
            provider: LLM provider name
            tokens_input: Input tokens consumed
            tokens_output: Output tokens generated
            model: Model ID used

        Returns:
            float: Actual cost in USD
        """
        with self.lock:
            # Get pricing for this provider
            pricing = PROVIDER_PRICING.get(provider)
            if not pricing:
                logger.warning(f"⚠️  Unknown provider: {provider}, assuming free")
                pricing = TokenPricing(provider, 0.0, 0.0)

            # Calculate cost
            input_cost = (tokens_input / 1_000_000) * pricing.input_cost_per_m
            output_cost = (tokens_output / 1_000_000) * pricing.output_cost_per_m
            total_cost = input_cost + output_cost

            # Create record
            record = InferenceRecord(
                task_id=task_id,
                provider=provider,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                total_tokens=tokens_input + tokens_output,
                timestamp=datetime.utcnow().isoformat(),
                cost=round(total_cost, 6),
                model=model,
            )

            # Store
            self.inferences.append(record)
            self.task_costs[task_id].append(record)
            self.provider_usage[provider] += 1

            logger.info(
                f"📊 Recorded: {provider} | "
                f"Task {task_id} | "
                f"Tokens: {record.total_tokens} | "
                f"Cost: ${record.cost:.6f}"
            )

            return total_cost

    def get_task_cost(self, task_id: str) -> Dict[str, Any]:
        """Get total cost breakdown for a specific task."""
        with self.lock:
            records = self.task_costs.get(task_id, [])

            if not records:
                return {
                    "task_id": task_id,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "inferences": [],
                    "providers_used": [],
                }

            total_cost = sum(r.cost for r in records)
            total_tokens = sum(r.total_tokens for r in records)
            providers = list(set(r.provider for r in records))

            return {
                "task_id": task_id,
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "inference_count": len(records),
                "inferences": [r.to_dict() for r in records],
                "providers_used": providers,
                "baseline_cost": self._calculate_baseline_cost(records),
                "savings": self._calculate_savings(total_cost, records),
            }

    def get_daily_summary(self, days_back: int = 1) -> Dict[str, Any]:
        """Get cost summary for last N days."""
        with self.lock:
            cutoff = datetime.utcnow() - timedelta(days=days_back)
            cutoff_iso = cutoff.isoformat()

            recent = [r for r in self.inferences if r.timestamp >= cutoff_iso]

            if not recent:
                return {
                    "period": f"last_{days_back}_days",
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "inference_count": 0,
                    "by_provider": {},
                    "by_day": {},
                }

            # Group by day
            by_day = defaultdict(list)
            for record in recent:
                day = record.timestamp.split("T")[0]
                by_day[day].append(record)

            total_cost = sum(r.cost for r in recent)
            total_tokens = sum(r.total_tokens for r in recent)

            # Provider breakdown
            by_provider = defaultdict(lambda: {"cost": 0.0, "tokens": 0, "count": 0})
            for record in recent:
                by_provider[record.provider]["cost"] += record.cost
                by_provider[record.provider]["tokens"] += record.total_tokens
                by_provider[record.provider]["count"] += 1

            # Daily breakdown
            daily_stats = {}
            for day, records in by_day.items():
                daily_stats[day] = {
                    "cost": round(sum(r.cost for r in records), 6),
                    "tokens": sum(r.total_tokens for r in records),
                    "inferences": len(records),
                }

            return {
                "period": f"last_{days_back}_days",
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "inference_count": len(recent),
                "baseline_cost": self._calculate_baseline_cost(recent),
                "actual_savings": round(
                    self._calculate_baseline_cost(recent) - total_cost, 6
                ),
                "savings_percentage": round(
                    (
                        (self._calculate_baseline_cost(recent) - total_cost)
                        / self._calculate_baseline_cost(recent)
                    )
                    * 100
                    if self._calculate_baseline_cost(recent) > 0
                    else 0
                ),
                "by_provider": dict(
                    (k, {**v, "cost": round(v["cost"], 6)})
                    for k, v in by_provider.items()
                ),
                "by_day": daily_stats,
            }

    def get_provider_breakdown(self) -> Dict[str, Any]:
        """Get provider usage distribution."""
        with self.lock:
            if not self.inferences:
                return {"providers": {}, "total_inferences": 0}

            provider_stats = defaultdict(
                lambda: {"cost": 0.0, "tokens": 0, "count": 0}
            )

            for record in self.inferences:
                provider_stats[record.provider]["cost"] += record.cost
                provider_stats[record.provider]["tokens"] += record.total_tokens
                provider_stats[record.provider]["count"] += 1

            total_cost = sum(r.cost for r in self.inferences)
            total_inferences = len(self.inferences)

            return {
                "providers": dict(
                    (k, {
                        **v,
                        "cost": round(v["cost"], 6),
                        "percentage_of_total": round(
                            (v["cost"] / total_cost * 100) if total_cost > 0 else 0
                        ),
                    })
                    for k, v in provider_stats.items()
                ),
                "total_cost": round(total_cost, 6),
                "total_inferences": total_inferences,
                "free_tier_percentage": round(
                    (
                        (provider_stats["Groq (Llama 3.3 70B)"]["count"] / total_inferences * 100)
                        if total_inferences > 0
                        else 0
                    )
                ),
            }

    def get_global_summary(self) -> Dict[str, Any]:
        """Get overall cost summary since tracker started."""
        with self.lock:
            if not self.inferences:
                return {
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "total_inferences": 0,
                    "total_tasks": 0,
                    "baseline_cost": 0.0,
                    "savings": 0.0,
                    "savings_percentage": 0.0,
                }

            total_cost = sum(r.cost for r in self.inferences)
            total_tokens = sum(r.total_tokens for r in self.inferences)
            baseline_cost = self._calculate_baseline_cost(self.inferences)

            return {
                "total_cost": round(total_cost, 6),
                "total_tokens": total_tokens,
                "total_inferences": len(self.inferences),
                "total_tasks": len(self.task_costs),
                "baseline_cost_gpt4o": round(baseline_cost, 6),
                "actual_savings_dollars": round(baseline_cost - total_cost, 6),
                "savings_percentage": round(
                    ((baseline_cost - total_cost) / baseline_cost * 100)
                    if baseline_cost > 0
                    else 0
                ),
                "average_cost_per_task": round(
                    total_cost / len(self.task_costs) if self.task_costs else 0, 6
                ),
                "average_tokens_per_task": round(
                    total_tokens / len(self.task_costs) if self.task_costs else 0
                ),
            }

    def get_recent_inferences(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most recent inferences."""
        with self.lock:
            return [r.to_dict() for r in self.inferences[-limit:]]

    def export_to_json(self, filepath: str):
        """Export all records to JSON file."""
        with self.lock:
            data = {
                "exported_at": datetime.utcnow().isoformat(),
                "summary": self.get_global_summary(),
                "inferences": [r.to_dict() for r in self.inferences],
            }

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"✅ Exported {len(self.inferences)} records to {filepath}")

    def clear_old_records(self, days: int = 30):
        """Clear records older than N days."""
        with self.lock:
            cutoff = datetime.utcnow() - timedelta(days=days)
            cutoff_iso = cutoff.isoformat()

            initial_count = len(self.inferences)
            self.inferences = [r for r in self.inferences if r.timestamp >= cutoff_iso]
            removed_count = initial_count - len(self.inferences)

            logger.info(f"🗑️  Removed {removed_count} old records")

    def _calculate_baseline_cost(self, records: List[InferenceRecord]) -> float:
        """Calculate what it would cost if all used GPT-4o."""
        total = 0.0
        for r in records:
            input_cost = (r.tokens_input / 1_000_000) * BASELINE_PRICING.input_cost_per_m
            output_cost = (r.tokens_output / 1_000_000) * BASELINE_PRICING.output_cost_per_m
            total += input_cost + output_cost
        return total

    def _calculate_savings(
        self, actual_cost: float, records: List[InferenceRecord]
    ) -> Dict[str, Any]:
        """Calculate savings vs baseline."""
        baseline = self._calculate_baseline_cost(records)
        savings = baseline - actual_cost
        percentage = (savings / baseline * 100) if baseline > 0 else 0

        return {
            "baseline_cost": round(baseline, 6),
            "actual_cost": round(actual_cost, 6),
            "savings_dollars": round(savings, 6),
            "savings_percentage": round(percentage, 2),
        }


# Global singleton instance
cost_tracker = CostTracker()
