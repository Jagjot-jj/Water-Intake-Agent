"""Unit tests for Water Intake Coach tools, memory, and agent loop.

Tests required by assignment checklist:
- logging valid water amount
- rejecting negative water amount
- rejecting zero water amount
- calculating remaining water
- calculating percentage
- detecting goal reached
- detecting goal exceeded
- memory persistence across turns
- multiple tool calls
- agent maximum-step protection
"""
import pytest
from datetime import date, timedelta
from config import DEFAULT_DAILY_GOAL_ML, MAX_AGENT_STEPS
from memory import ConversationMemory
from tools import get_progress, log_water, set_daily_goal
from agent import WaterIntakeAgent


class TestWaterCoachTools:
    """Test suite verifying tool operations, boundary conditions, and state transitions."""

    def test_log_water_valid(self):
        """Test logging valid water amount updates memory and returns correct structure."""
        mem = ConversationMemory(daily_goal_ml=2500)
        res = log_water(500, mem)

        assert res["status"] == "success"
        assert res["logged_ml"] == 500
        assert res["total_ml"] == 500
        assert res["remaining_ml"] == 2000
        assert res["progress_percent"] == 20.0
        assert res["goal_met"] is False
        assert res["goal_exceeded"] is False
        assert mem.today_intake_ml == 500

    def test_reject_negative_water_amount(self):
        """Test that negative water amounts are strictly rejected without modifying state."""
        mem = ConversationMemory(daily_goal_ml=2500)
        mem.record_intake(400)

        res = log_water(-250, mem)
        assert res["status"] == "error"
        assert res["error_type"] == "negative_or_zero"
        assert mem.today_intake_ml == 400  # State unchanged

    def test_reject_zero_water_amount(self):
        """Test that zero water amount is rejected."""
        mem = ConversationMemory(daily_goal_ml=2500)
        res = log_water(0, mem)
        assert res["status"] == "error"
        assert res["error_type"] == "negative_or_zero"
        assert mem.today_intake_ml == 0

    def test_calculate_remaining_and_percentage(self):
        """Test accurate remaining volume and completion percentage calculations."""
        mem = ConversationMemory(daily_goal_ml=2000)
        log_water(750, mem)
        progress = get_progress(mem)

        assert progress["today_intake_ml"] == 750
        assert progress["daily_goal_ml"] == 2000
        assert progress["remaining_ml"] == 1250
        assert progress["progress_percent"] == 37.5
        assert progress["goal_met"] is False

    def test_detect_goal_reached(self):
        """Test boundary condition when intake exactly equals daily goal."""
        mem = ConversationMemory(daily_goal_ml=2500)
        log_water(1500, mem)
        res = log_water(1000, mem)

        assert res["total_ml"] == 2500
        assert res["remaining_ml"] == 0
        assert res["progress_percent"] == 100.0
        assert res["goal_met"] is True
        assert res["goal_exceeded"] is False

    def test_detect_goal_exceeded(self):
        """Test boundary condition when intake exceeds daily goal."""
        mem = ConversationMemory(daily_goal_ml=2500)
        log_water(2800, mem)
        progress = get_progress(mem)

        assert progress["today_intake_ml"] == 2800
        assert progress["remaining_ml"] == 0
        assert progress["progress_percent"] == 112.0
        assert progress["goal_met"] is True
        assert progress["goal_exceeded"] is True

    def test_memory_persistence_across_turns(self):
        """Test that conversation memory accumulates intake across multiple agent turns."""
        agent = WaterIntakeAgent()
        
        # Turn 1: User logs 500 ml
        turn1 = agent.run("I drank 500 ml of water.")
        assert agent.memory.today_intake_ml == 500
        assert len(agent.memory.history) == 1

        # Turn 2: User adds 300 ml
        turn2 = agent.run("I drank another 300 ml.")
        assert agent.memory.today_intake_ml == 800
        assert len(agent.memory.history) == 2

        # Turn 3: User queries progress without logging
        turn3 = agent.run("How much have I had today?")
        assert agent.memory.today_intake_ml == 800
        assert "800" in turn3["response"]
        assert len(agent.memory.history) == 3

    def test_agent_historical_log_does_not_change_today(self):
        """The agent should attribute yesterday's intake to yesterday."""
        agent = WaterIntakeAgent()
        agent.run("I drank 100 ml today")
        result = agent.run("I had 250 ml last day")

        assert agent.memory.today_intake_ml == 100
        assert "yesterday" in result["response"].lower()

    def test_agent_future_log_does_not_change_today(self):
        """The agent should attribute planned tomorrow intake to tomorrow."""
        agent = WaterIntakeAgent()
        agent.run("I drank 100 ml today")
        result = agent.run("I will drink 100 ml tommorrow")

        assert agent.memory.today_intake_ml == 100
        assert "tomorrow" in result["response"].lower()

    def test_agent_supports_extended_relative_dates(self):
        """Extended relative dates are resolved without changing today's total."""
        agent = WaterIntakeAgent()
        result = agent.run("I had 250 ml ereyesterday")

        assert agent.memory.today_intake_ml == 0
        assert "day before yesterday" in result["response"].lower()

    def test_agent_supports_next_week_timeline(self):
        """Next week is scheduled seven days ahead instead of counted today."""
        agent = WaterIntakeAgent()
        result = agent.run("I will drink 250 ml next week")

        assert agent.memory.today_intake_ml == 0
        assert agent.memory.logs[-1]["date"] == (date.today() + timedelta(days=7)).isoformat()
        assert "next week" in result["response"].lower()

    def test_agent_supports_relative_and_explicit_dates(self):
        """Supported week, month, and ISO date methods are logged for their dates."""
        agent = WaterIntakeAgent()
        result = agent.run("I had 250 ml on 2026-09-15")

        assert agent.memory.today_intake_ml == 0
        assert agent.memory.logs[-1]["date"] == "2026-09-15"
        assert "2026-09-15" in result["response"]

    def test_multiple_tool_calls_in_agent_loop(self):
        """Verify the agent executes multiple tools (e.g. log_water + get_progress) in a single turn."""
        agent = WaterIntakeAgent()
        output = agent.run("I just drank 600 ml of water.")
        
        tool_call_steps = [s for s in output["trace"] if s.get("type") == "tool_call"]
        tools_called = [s["tool"] for s in tool_call_steps]

        assert "log_water" in tools_called
        assert "get_progress" in tools_called
        assert len(tool_call_steps) >= 2

    def test_agent_max_step_protection(self):
        """Verify the agent bounds its execution steps by MAX_AGENT_STEPS."""
        agent = WaterIntakeAgent()
        output = agent.run("Please log 400 ml and evaluate my hydration.")
        assert len(output["trace"]) <= MAX_AGENT_STEPS + 2
        assert output["response"] != ""

    def test_set_daily_goal_utility(self):
        """Test setting custom daily goal."""
        mem = ConversationMemory(daily_goal_ml=2500)
        res = set_daily_goal(3000, mem)
        assert res["status"] == "success"
        assert res["new_goal_ml"] == 3000
        assert mem.daily_goal_ml == 3000

    def test_historical_log_does_not_change_today(self):
        """Logs explicitly attributed to yesterday must not count toward today's goal."""
        mem = ConversationMemory(daily_goal_ml=2500)
        log_water(100, mem)
        log_water(250, mem, date.today() - timedelta(days=1))

        progress = get_progress(mem)
        assert progress["today_intake_ml"] == 100
        assert mem.logs[-1]["date"] == (date.today() - timedelta(days=1)).isoformat()
