"""
Test script demonstrating cost tracking functionality.
Simulates various LLM provider usage and shows cost calculations.
"""

import sys
from cost_tracker import cost_tracker, PROVIDER_PRICING, BASELINE_PRICING
from datetime import datetime, timedelta
import json

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def simulate_inferences():
    """Simulate various LLM inferences to test cost tracking."""

    print_header("SIMULATING LLM INFERENCES")

    # Scenario: Processing 10 tasks
    inferences = [
        # Task 1: Groq (fast, simple task)
        {
            "task_id": "task_001",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 500,
            "tokens_output": 150,
            "model": "llama-3.3-70b-versatile",
        },
        # Task 2: Groq (vision task)
        {
            "task_id": "task_002",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 2500,
            "tokens_output": 300,
            "model": "llama-3.3-70b-versatile",
        },
        # Task 3: Anthropic (fallback - harder task)
        {
            "task_id": "task_003",
            "provider": "Anthropic Claude 3.5",
            "tokens_input": 1200,
            "tokens_output": 400,
            "model": "claude-3-5-sonnet-20241022",
        },
        # Task 4-8: Groq
        {
            "task_id": "task_004",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 800,
            "tokens_output": 200,
            "model": "llama-3.3-70b-versatile",
        },
        {
            "task_id": "task_005",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 600,
            "tokens_output": 180,
            "model": "llama-3.3-70b-versatile",
        },
        {
            "task_id": "task_006",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 900,
            "tokens_output": 250,
            "model": "llama-3.3-70b-versatile",
        },
        {
            "task_id": "task_007",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 700,
            "tokens_output": 220,
            "model": "llama-3.3-70b-versatile",
        },
        {
            "task_id": "task_008",
            "provider": "OpenAI GPT-4V",
            "tokens_input": 1500,
            "tokens_output": 350,
            "model": "gpt-4-vision-preview",
        },
        {
            "task_id": "task_009",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 1000,
            "tokens_output": 300,
            "model": "llama-3.3-70b-versatile",
        },
        {
            "task_id": "task_010",
            "provider": "Groq (Llama 3.3 70B)",
            "tokens_input": 750,
            "tokens_output": 180,
            "model": "llama-3.3-70b-versatile",
        },
    ]

    # Record all inferences
    for inf in inferences:
        cost = cost_tracker.record_inference(
            task_id=inf["task_id"],
            provider=inf["provider"],
            tokens_input=inf["tokens_input"],
            tokens_output=inf["tokens_output"],
            model=inf["model"],
        )
        print(f"✅ {inf['task_id']}: {inf['provider']:<30} | Cost: ${cost:.6f}")


def show_task_breakdown():
    """Show cost breakdown for individual tasks."""
    print_header("TASK COST BREAKDOWN")

    for task_id in [f"task_{i:03d}" for i in range(1, 11)]:
        task_data = cost_tracker.get_task_cost(task_id)
        print(f"\n{task_id}:")
        print(f"  Provider: {task_data['providers_used']}")
        print(f"  Tokens: {task_data['total_tokens']:,}")
        print(f"  Actual Cost: ${task_data['total_cost']:.6f}")
        print(f"  If using GPT-4o: ${task_data['baseline_cost']:.6f}")
        print(f"  Savings: ${task_data['savings']['savings_dollars']:.6f} ({task_data['savings']['savings_percentage']:.1f}%)")


def show_provider_breakdown():
    """Show provider usage distribution."""
    print_header("PROVIDER USAGE BREAKDOWN")

    breakdown = cost_tracker.get_provider_breakdown()

    print(f"Total Inferences: {breakdown['total_inferences']}")
    print(f"Total Cost: ${breakdown['total_cost']:.6f}\n")

    for provider, stats in breakdown["providers"].items():
        print(f"{provider}:")
        print(f"  Calls: {stats['count']}")
        print(f"  Tokens: {stats['tokens']:,}")
        print(f"  Cost: ${stats['cost']:.6f}")
        print(f"  % of Total: {stats['percentage_of_total']:.1f}%\n")

    print(f"Free Tier Usage: {breakdown['free_tier_percentage']:.1f}%")


def show_global_summary():
    """Show global cost summary and savings."""
    print_header("GLOBAL COST SUMMARY")

    summary = cost_tracker.get_global_summary()

    print(f"Total Inferences: {summary['total_inferences']}")
    print(f"Total Tasks: {summary['total_tasks']}")
    print(f"Total Tokens: {summary['total_tokens']:,}\n")

    print(f"Actual Cost (using mixed providers): ${summary['total_cost']:.6f}")
    print(f"Baseline Cost (if all GPT-4o):     ${summary['baseline_cost_gpt4o']:.6f}")
    print(f"Total Savings:                     ${summary['actual_savings_dollars']:.6f}")
    print(f"Savings Percentage:                {summary['savings_percentage']:.1f}%\n")

    print(f"Average Cost per Task: ${summary['average_cost_per_task']:.6f}")
    print(f"Average Tokens per Task: {summary['average_tokens_per_task']}")


def show_daily_summary():
    """Show daily cost breakdown."""
    print_header("DAILY COST SUMMARY")

    daily = cost_tracker.get_daily_summary(days_back=1)

    print(f"Period: {daily['period']}")
    print(f"Total Inferences: {daily['inference_count']}")
    print(f"Total Tokens: {daily['total_tokens']:,}")
    print(f"Total Cost: ${daily['total_cost']:.6f}")
    print(f"Baseline Cost: ${daily['baseline_cost']:.6f}")
    print(f"Actual Savings: ${daily['actual_savings']:.6f}")
    print(f"Savings Percentage: {daily['savings_percentage']:.1f}%\n")

    print("By Provider:")
    for provider, stats in daily['by_provider'].items():
        print(f"  {provider}: ${stats['cost']:.6f} ({stats['count']} inferences)")


def show_roi_analysis():
    """Show return on investment analysis."""
    print_header("ROI ANALYSIS: FREE TIER VS PREMIUM")

    summary = cost_tracker.get_global_summary()
    breakdown = cost_tracker.get_provider_breakdown()

    groq_calls = breakdown['providers'].get('Groq (Llama 3.3 70B)', {}).get('count', 0)
    groq_cost = breakdown['providers'].get('Groq (Llama 3.3 70B)', {}).get('cost', 0)

    total_calls = summary['total_inferences']
    free_tier_percentage = (groq_calls / total_calls * 100) if total_calls > 0 else 0

    print(f"Strategy: Smart Routing (Free First → Paid Fallback)")
    print(f"\nResults:")
    print(f"  ✅ Used free tier (Groq): {groq_calls}/{total_calls} calls ({free_tier_percentage:.0f}%)")
    print(f"  ✅ Free tier cost: ${groq_cost:.6f}")
    print(f"  ✅ Paid tier fallback: {total_calls - groq_calls} calls")
    print(f"  ✅ Total cost: ${summary['total_cost']:.6f}")
    print(f"  ✅ Savings vs all-paid: ${summary['actual_savings_dollars']:.6f} ({summary['savings_percentage']:.1f}%)")

    print(f"\nComparison to Orchestrator Paper:")
    print(f"  Target savings: 75-85%")
    print(f"  Achieved savings: {summary['savings_percentage']:.1f}%")
    if summary['savings_percentage'] >= 75:
        print(f"  ✅ GOAL MET! Achieved target savings range.")
    else:
        print(f"  ⚠️  Below target. Consider increasing free tier usage.")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  AGENT-S3 COST TRACKING SYSTEM TEST")
    print("="*60)

    # Simulate inferences
    simulate_inferences()

    # Show various views
    show_task_breakdown()
    show_provider_breakdown()
    show_global_summary()
    show_daily_summary()
    show_roi_analysis()

    # Export metrics
    print_header("EXPORTING METRICS")
    export_path = "/tmp/agent_s3_test_metrics.json"
    cost_tracker.export_to_json(export_path)
    print(f"✅ Metrics exported to: {export_path}")

    # Show pricing reference
    print_header("PROVIDER PRICING REFERENCE")
    for provider, pricing in PROVIDER_PRICING.items():
        print(f"{provider}:")
        print(f"  Input:  ${pricing.input_cost_per_m:.2f}/M tokens")
        print(f"  Output: ${pricing.output_cost_per_m:.2f}/M tokens")

    print(f"\nBaseline (comparison):")
    print(f"  Provider: GPT-4o (assumed baseline)")
    print(f"  Input:  ${BASELINE_PRICING.input_cost_per_m:.2f}/M tokens")
    print(f"  Output: ${BASELINE_PRICING.output_cost_per_m:.2f}/M tokens")

    print("\n" + "="*60)
    print("✅ Test Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
