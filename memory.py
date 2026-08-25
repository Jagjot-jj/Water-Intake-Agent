"""Conversation Memory implementation for the Water Intake Coach Agent.

Maintains multi-turn state including daily goal, total intake, historical logs,
and turn traces across the conversation session.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from config import DEFAULT_DAILY_GOAL_ML


class ConversationMemory:
    """Stores and manages conversation state and hydration history across multiple turns."""

    def __init__(self, daily_goal_ml: int = DEFAULT_DAILY_GOAL_ML):
        self.daily_goal_ml: int = daily_goal_ml
        self.today_intake_ml: int = 0
        self.logs: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []

    def record_intake(self, amount_ml: int) -> Dict[str, Any]:
        """Record a verified water intake amount and store the log entry."""
        self.today_intake_ml += amount_ml
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "amount_ml": amount_ml,
            "running_total_ml": self.today_intake_ml
        }
        self.logs.append(log_entry)
        return log_entry

    def set_goal(self, new_goal_ml: int) -> None:
        """Update the daily water intake target."""
        if new_goal_ml <= 0:
            raise ValueError("Daily goal must be a positive number greater than 0.")
        self.daily_goal_ml = new_goal_ml

    def add_turn(self, user_message: str, plan: str, steps: List[Dict[str, Any]], final_response: str) -> None:
        """Record an entire agent interaction turn with trace and outcome."""
        turn_entry = {
            "turn_index": len(self.history) + 1,
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "plan": plan,
            "steps": steps,
            "final_response": final_response,
            "intake_at_turn": self.today_intake_ml,
            "goal_at_turn": self.daily_goal_ml
        }
        self.history.append(turn_entry)

    def get_state(self) -> Dict[str, Any]:
        """Return the current hydration state snapshot."""
        remaining_ml = max(0, self.daily_goal_ml - self.today_intake_ml)
        progress_percent = round((self.today_intake_ml / self.daily_goal_ml) * 100, 1) if self.daily_goal_ml > 0 else 0.0
        return {
            "daily_goal_ml": self.daily_goal_ml,
            "today_intake_ml": self.today_intake_ml,
            "remaining_ml": remaining_ml,
            "progress_percent": progress_percent,
            "goal_met": self.today_intake_ml >= self.daily_goal_ml,
            "goal_exceeded": self.today_intake_ml > self.daily_goal_ml,
            "total_logs": len(self.logs),
            "total_turns": len(self.history)
        }

    def reset(self, daily_goal_ml: Optional[int] = None) -> None:
        """Reset all today's intake and history."""
        self.daily_goal_ml = daily_goal_ml if daily_goal_ml is not None else DEFAULT_DAILY_GOAL_ML
        self.today_intake_ml = 0
        self.logs = []
        self.history = []

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory state for inspection and logging."""
        return {
            "daily_goal_ml": self.daily_goal_ml,
            "today_intake_ml": self.today_intake_ml,
            "logs": self.logs,
            "history_count": len(self.history),
            "state": self.get_state()
        }
