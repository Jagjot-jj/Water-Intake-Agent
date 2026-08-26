"""Core tool implementations for the Water Intake Coach AI Agent.

Provides:
1. log_water(ml): Records user water intake with input validation and progress stats.
2. get_progress(): Fetches current hydration metrics, percentages, and goal status.
3. set_daily_goal(ml): Optional goal configuration utility.
"""
from datetime import date
from typing import Any, Dict, Optional
from memory import ConversationMemory


def log_water(ml: int, memory: ConversationMemory, intake_date: Optional[date] = None) -> Dict[str, Any]:
    """Record water consumption in milliliters and update memory state.

    Args:
        ml (int): Amount of water in milliliters. Must be positive.
        memory (ConversationMemory): Active conversation state tracker.

    Returns:
        Dict[str, Any]: Structured execution output containing progress metrics.
    """
    if memory is None:
        raise ValueError("A valid ConversationMemory instance must be provided.")

    if not isinstance(ml, (int, float)):
        return {
            "status": "error",
            "error_type": "invalid_type",
            "message": f"Invalid water amount: '{ml}'. Amount must be a positive integer."
        }

    amount = int(ml)
    if amount <= 0:
        return {
            "status": "error",
            "error_type": "negative_or_zero",
            "message": f"Cannot log {amount} ml. Amount must be strictly greater than 0 ml."
        }

    if amount > 5000:
        return {
            "status": "error",
            "error_type": "excessive_single_intake",
            "message": (
                f"Single log of {amount} ml seems unusually large for one intake. "
                "Please verify the amount."
            )
        }

    # Record intake in conversation memory
    logged_date = intake_date or date.today()
    memory.record_intake(amount, logged_date)
    total = memory.today_intake_ml
    goal = memory.daily_goal_ml
    remaining = max(0, goal - total)
    percent = round((total / goal) * 100, 1) if goal > 0 else 0.0
    goal_met = total >= goal
    goal_exceeded = total > goal

    return {
        "status": "success",
        "logged_ml": amount,
        "total_ml": total,
        "goal_ml": goal,
        "remaining_ml": remaining,
        "progress_percent": percent,
        "goal_met": goal_met,
        "goal_exceeded": goal_exceeded,
        "date": logged_date.isoformat(),
        "message": (
            f"Logged {amount} ml for {logged_date.isoformat()}. "
            f"Total today is {total}/{goal} ml ({percent}%)."
        )
    }


def get_progress(memory: ConversationMemory) -> Dict[str, Any]:
    """Retrieve current hydration totals, remaining target, and completion status.

    Args:
        memory (ConversationMemory): Active conversation state tracker.

    Returns:
        Dict[str, Any]: Structured hydration status report.
    """
    if memory is None:
        raise ValueError("A valid ConversationMemory instance must be provided.")

    total = memory.today_intake_ml
    goal = memory.daily_goal_ml
    remaining = max(0, goal - total)
    percent = round((total / goal) * 100, 1) if goal > 0 else 0.0
    goal_met = total >= goal
    goal_exceeded = total > goal

    return {
        "status": "success",
        "today_intake_ml": total,
        "daily_goal_ml": goal,
        "remaining_ml": remaining,
        "progress_percent": percent,
        "goal_met": goal_met,
        "goal_exceeded": goal_exceeded,
        "date": date.today().isoformat(),
        "log_count": len(memory.logs)
    }


def set_daily_goal(ml: int, memory: ConversationMemory) -> Dict[str, Any]:
    """Update the daily water intake target in milliliters.

    Args:
        ml (int): New daily target in milliliters. Must be positive.
        memory (ConversationMemory): Active conversation state tracker.

    Returns:
        Dict[str, Any]: Confirmation of updated goal and recalibrated metrics.
    """
    if memory is None:
        raise ValueError("A valid ConversationMemory instance must be provided.")

    if not isinstance(ml, (int, float)) or int(ml) <= 0:
        return {
            "status": "error",
            "message": "Daily target must be a positive integer in milliliters."
        }

    new_goal = int(ml)
    memory.set_goal(new_goal)
    progress = get_progress(memory)

    return {
        "status": "success",
        "new_goal_ml": new_goal,
        "today_intake_ml": progress["today_intake_ml"],
        "remaining_ml": progress["remaining_ml"],
        "progress_percent": progress["progress_percent"],
        "message": f"Daily target updated to {new_goal} ml."
    }


# Gemini Tool Function Declarations
TOOL_DECLARATIONS = [
    {
        "name": "log_water",
        "description": "Records water intake in milliliters (ml) for the user and calculates current progress towards daily goal.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "ml": {
                    "type": "INTEGER",
                    "description": "Amount of water consumed in milliliters (e.g., 250, 500, 750)."
                }
            },
            "required": ["ml"]
        }
    },
    {
        "name": "get_progress",
        "description": "Fetches the user's current water intake progress, total ml consumed today, remaining ml needed, and completion percentage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "set_daily_goal",
        "description": "Configures or updates the user's daily water intake target in milliliters (default is 2500 ml).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "ml": {
                    "type": "INTEGER",
                    "description": "New target hydration amount in milliliters (e.g., 2000, 2500, 3000)."
                }
            },
            "required": ["ml"]
        }
    }
]
