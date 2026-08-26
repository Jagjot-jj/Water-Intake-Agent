"""AI Agent implementation for the Water Intake Coach.

Architecture:
  Plan-Act-Observe-Decide Loop
  1. Analyze user request and formulate plan.
  2. Select and execute tool(s) (e.g. log_water, get_progress).
  3. Observe structured tool outputs.
  4. Evaluate progress and decide if further actions are required.
  5. Formulate grounded, gentle, non-medical final response with health disclaimer.
  6. Record complete trace and persist in conversation memory.
"""
import json
import copy
import os
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from config import GEMINI_MODEL, HEALTH_DISCLAIMER, MAX_AGENT_STEPS
from memory import ConversationMemory
from tools import get_progress, log_water, set_daily_goal

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class WaterIntakeAgent:
    """Agent that coaches users to reach their daily water intake goal through a plan-act loop."""

    def __init__(self, memory: Optional[ConversationMemory] = None, api_key: Optional[str] = None):
        self.memory = memory if memory is not None else ConversationMemory()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = None

        if self.api_key and GENAI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Agent Init Warning] Could not initialize Gemini client: {e}")

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python tool and return structured dictionary result."""
        if tool_name == "log_water":
            ml = tool_args.get("ml", 0)
            intake_date = tool_args.get("intake_date")
            return log_water(ml, self.memory, date.fromisoformat(intake_date) if intake_date else None)
        elif tool_name == "get_progress":
            return get_progress(self.memory)
        elif tool_name == "set_daily_goal":
            ml = tool_args.get("ml", 2500)
            return set_daily_goal(ml, self.memory)
        else:
            return {
                "status": "error",
                "message": f"Unknown tool '{tool_name}'"
            }

    @staticmethod
    def _intake_date_from_text(user_lower: str) -> tuple[Optional[date], bool, str]:
        """Resolve supported relative or ISO dates without inferring an unspecified date."""
        supported_dates = [
            (r"\b(day\s+before\s+yesterday|ereyesterday)\b", -2, "the day before yesterday"),
            (r"\b(day\s+after\s+tomorrow|overmorrow)\b", 2, "the day after tomorrow"),
            (r"\b(yesterday|last\s+day)\b", -1, "yesterday"),
            (r"\b(today)\b", 0, "today"),
            (r"\b(tomorrow|tommorrow)\b", 1, "tomorrow"),
        ]
        for pattern, offset, label in supported_dates:
            if re.search(pattern, user_lower):
                return date.today() + timedelta(days=offset), True, label

        iso_match = re.search(r"\b(?:on|for)?\s*(\d{4}-\d{2}-\d{2})\b", user_lower)
        if iso_match:
            try:
                return date.fromisoformat(iso_match.group(1)), True, iso_match.group(1)
            except ValueError:
                return None, True, ""

        offset_match = re.search(r"\bin\s+(\d+)\s+(day|days|week|weeks)\b", user_lower)
        if offset_match:
            count = int(offset_match.group(1))
            multiplier = 7 if offset_match.group(2).startswith("week") else 1
            return date.today() + timedelta(days=count * multiplier), True, f"in {count} {offset_match.group(2)}"

        if re.search(r"\bnext\s+week\b", user_lower):
            return date.today() + timedelta(days=7), True, "next week"
        if re.search(r"\bnext\s+month\b", user_lower):
            month = date.today().month % 12 + 1
            year = date.today().year + (date.today().month == 12)
            day = min(date.today().day, [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
            return date(year, month, day), True, "next month"

        timeline_pattern = r"\b(last|this)\s+(week|month)\b"
        return None, bool(re.search(timeline_pattern, user_lower)), ""

    @staticmethod
    def _parse_amount_ml(user_lower: str) -> tuple[Optional[int], bool]:
        """Parse explicit supported volumes; the second value indicates ambiguity."""
        if re.search(r"\b(bottle|glass|cup|sip|sips)\b", user_lower) and not re.search(r"\d+(?:\.\d+)?\s*(?:ml|milliliters?|l|liters?)\b", user_lower):
            return None, True
        unit_pattern = r"(\d+(?:\.\d+)?)\s*(ml|milliliters?|l|liters?)\b"
        matches = re.findall(unit_pattern, user_lower)
        if matches:
            total = 0.0
            for value, unit in matches:
                total += float(value) * (1000 if unit.startswith("l") else 1)
            return round(total), False
        word_amounts = {
            "half a litre": 500, "half litre": 500, "one and a half litres": 1500,
            "one litre": 1000, "a litre": 1000, "two litres": 2000,
        }
        for phrase, amount in word_amounts.items():
            if phrase in user_lower:
                return amount, False
        return None, False

    @staticmethod
    def _is_hypothetical(user_lower: str) -> bool:
        return bool(re.search(r"\b(if|would|could|suppose|assuming)\b|\bhow much would\b|\bwill i reach\b", user_lower))

    def _rule_based_agent_loop(self, user_input: str) -> Dict[str, Any]:
        """Deterministic Plan-Act-Observe-Decide loop for offline testing or fallback."""
        trace: List[Dict[str, Any]] = []
        user_lower = user_input.lower().strip()

        # Step 1: Plan
        step_1 = {
            "step_number": 1,
            "type": "plan",
            "description": "Analyzed user message to identify hydration intent, quantities, and necessary tool steps."
        }
        trace.append(step_1)

        if re.search(r"\b(delete|remove|reset|clear|export|reminder|weekly average|monthly|database|history|last week|last month)\b", user_lower):
            response = "I can't perform that action because this coach only supports logging intake and checking today's progress."
            trace.append({"step_number": 2, "type": "decision", "description": "Declined an unsupported action without changing memory."})
            return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        if re.search(r"\b(ignore|pretend|assume|fake|invent|say that)\b", user_lower):
            response = "I can only report values returned by the stored progress state; I won't invent intake or tool results."
            trace.append({"step_number": 2, "type": "decision", "description": "Rejected an attempt to override grounded tool state."})
            return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        if re.search(r"\b(yesterday|ereyesterday|last week|last month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", user_lower) and re.search(r"\b(how much|what did i drink|intake|consumed)\b", user_lower) and not re.search(r"\b\d", user_lower):
            response = "I only have today's intake available; I don't have reliable historical totals for that date."
            trace.append({"step_number": 2, "type": "decision", "description": "Declined to fabricate unavailable historical intake."})
            return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        if self._is_hypothetical(user_lower):
            amount, ambiguous = self._parse_amount_ml(user_lower)
            if ambiguous:
                response = "Please provide the bottle, glass, or cup capacity in ml; I won't guess it."
            elif amount is not None:
                current = self.memory.get_state()
                projected = current["today_intake_ml"] + amount
                response = f"Hypothetically, {projected} ml would be {round((projected / current['daily_goal_ml']) * 100, 1)}% of your {current['daily_goal_ml']} ml goal. I did not log it."
            else:
                response = "Please provide the amount in ml or litres. I did not log anything."
            trace.append({"step_number": 2, "type": "decision", "description": "Answered hypothetically without calling log_water."})
            return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        if re.search(r"\b(?:oz|ounces?|gallons?|grams?)\b", user_lower):
            response = "I support water amounts in ml or litres only. Please convert the amount before logging it."
            trace.append({"step_number": 2, "type": "decision", "description": "Rejected an unsupported unit without conversion assumptions."})
            return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        # Check for goal update intent
        goal_match = re.search(r"(?:goal|target)\s*(?:is|to|=|set to)?\s*(\d+)\s*(?:ml)?", user_lower)
        if "goal" in user_lower and goal_match and not ("drank" in user_lower or "logged" in user_lower):
            target_ml = int(goal_match.group(1))
            trace.append({
                "step_number": 2,
                "type": "tool_call",
                "tool": "set_daily_goal",
                "arguments": {"ml": target_ml}
            })
            result = self.execute_tool("set_daily_goal", {"ml": target_ml})
            trace.append({
                "step_number": 3,
                "type": "tool_result",
                "tool": "set_daily_goal",
                "result": result
            })
            trace.append({
                "step_number": 4,
                "type": "observation",
                "description": f"Daily target updated to {target_ml} ml."
            })
            response = (
                f"I have updated your daily water intake goal to {target_ml} ml. "
                f"You currently have {result['today_intake_ml']} ml recorded today with "
                f"{result['remaining_ml']} ml remaining ({result['progress_percent']}%)."
            )
            return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        # Check for water logging intent
        # Match patterns like: "500 ml", "drank 300", "500ml", "had 250 ml", "another 300 ml"
        log_match = re.search(r"(?:drank|had|logged|add|plus|another)?\s*(\d+)\s*(?:ml|milliliters)?", user_lower)
        explicit_log_keywords = ["drank", "had", "logged", "drinking", "consumed", "another", "ml", "milliliter", "glass", "cup", "bottle"]
        has_log_intent = any(kw in user_lower for kw in explicit_log_keywords) or re.search(r"\b\d+\s*ml\b", user_lower)

        amount_to_log = None
        if has_log_intent:
            amount_to_log, ambiguous_amount = self._parse_amount_ml(user_lower)
            if ambiguous_amount:
                clarification = "How many ml was the glass, bottle, cup, or sip? I won't assume a container size."
                trace.append({"step_number": 2, "type": "decision", "description": "Requested an explicit volume for an ambiguous quantity."})
                return {"final_response": clarification, "trace": trace, "plan": step_1["description"]}

            if amount_to_log is not None and (amount_to_log <= 0 or amount_to_log > 5000):
                response = "Please provide a positive water amount no greater than 5000 ml per log."
                trace.append({"step_number": 2, "type": "decision", "description": "Rejected an invalid or excessive amount before tool execution."})
                return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        if amount_to_log is not None:
            intake_date, has_timeline, timeline_label = self._intake_date_from_text(user_lower)
            if has_timeline and intake_date is None:
                clarification = "I can log water for a specific date, but I don't recognize that timeline. Please say today, yesterday, tomorrow, or provide an ISO date like 2026-08-28."
                trace.append({"step_number": len(trace) + 1, "type": "decision", "description": "Requested clarification because the timeline was not supported."})
                return {"final_response": clarification, "trace": trace, "plan": step_1["description"]}
            is_historical = intake_date is not None and intake_date < date.today()
            is_future = intake_date is not None and intake_date > date.today()
            # Step 2: Act (Tool Call: log_water)
            trace.append({
                "step_number": len(trace) + 1,
                "type": "tool_call",
                "tool": "log_water",
                "arguments": {"ml": amount_to_log, **({"intake_date": intake_date.isoformat()} if intake_date else {})}
            })
            log_res = self.execute_tool(
                "log_water",
                {"ml": amount_to_log, **({"intake_date": intake_date.isoformat()} if intake_date else {})}
            )
            trace.append({
                "step_number": len(trace) + 1,
                "type": "tool_result",
                "tool": "log_water",
                "result": log_res
            })

            # Step 3: Act (Tool Call: get_progress for comprehensive evaluation)
            trace.append({
                "step_number": len(trace) + 1,
                "type": "tool_call",
                "tool": "get_progress",
                "arguments": {}
            })
            progress_res = self.execute_tool("get_progress", {})
            trace.append({
                "step_number": len(trace) + 1,
                "type": "tool_result",
                "tool": "get_progress",
                "result": progress_res
            })

            # Step 4: Observation & Decision
            total = progress_res["today_intake_ml"]
            goal = progress_res["daily_goal_ml"]
            remaining = progress_res["remaining_ml"]
            percent = progress_res["progress_percent"]

            decision_notes = ""
            if progress_res["goal_exceeded"]:
                decision_notes = f"Daily goal exceeded ({total}/{goal} ml). Acknowledge achievement and advise not to over-hydrate."
                advice = (
                    f"Great job! You have exceeded your daily goal with {total} ml recorded "
                    f"({percent}% of your {goal} ml target). Remember that hydration needs vary and "
                    "there is no need to drink excessively."
                )
            elif progress_res["goal_met"]:
                decision_notes = f"Daily goal reached ({total}/{goal} ml). Celebrate completion."
                advice = (
                    f"Congratulations! You reached your daily goal of {goal} ml! "
                    f"You have logged {total} ml ({percent}%) so far today."
                )
            elif remaining <= 400:
                decision_notes = f"Very close to goal ({remaining} ml left). Provide gentle small nudge."
                advice = (
                    f"Logged {amount_to_log} ml! You're almost there: you have had {total} ml "
                    f"and only {remaining} ml left to reach your {goal} ml goal ({percent}% completed)."
                )
            else:
                decision_notes = f"Goal in progress ({remaining} ml remaining). Provide status update."
                advice = (
                    f"Logged {amount_to_log} ml. You've had {total} ml so far today, "
                    f"with {remaining} ml remaining to hit your {goal} ml goal ({percent}% completed)."
                )

            trace.append({
                "step_number": len(trace) + 1,
                "type": "decision",
                "description": decision_notes
            })

            if is_historical:
                advice = f"Logged {amount_to_log} ml for {timeline_label}. Today's total remains {total} ml ({percent}% of your {goal} ml goal)."
            elif is_future:
                advice = f"Scheduled {amount_to_log} ml for {timeline_label}. Today's total remains {total} ml ({percent}% of your {goal} ml goal)."
            return {"final_response": advice, "trace": trace, "plan": step_1["description"]}

        is_progress_question = bool(re.search(r"\b(how much|what is|what's|how many|progress|remaining|need)\b", user_lower))
        if has_log_intent and not is_progress_question and re.search(r"\b(?:drank|had|add|log|consumed)\b", user_lower):
            response = "Please provide a positive amount in ml or litres; I won't guess or log an unspecified amount."
            trace.append({"step_number": 2, "type": "decision", "description": "Requested an explicit supported quantity."})
            return {"final_response": response, "trace": trace, "plan": step_1["description"]}

        # Check for inquiry / progress check
        # e.g., "How much more do I need?", "How much have I had today?", "What is my progress?"
        trace.append({
            "step_number": len(trace) + 1,
            "type": "tool_call",
            "tool": "get_progress",
            "arguments": {}
        })
        progress_res = self.execute_tool("get_progress", {})
        trace.append({
            "step_number": len(trace) + 1,
            "type": "tool_result",
            "tool": "get_progress",
            "result": progress_res
        })

        total = progress_res["today_intake_ml"]
        goal = progress_res["daily_goal_ml"]
        remaining = progress_res["remaining_ml"]
        percent = progress_res["progress_percent"]

        trace.append({
            "step_number": len(trace) + 1,
            "type": "decision",
            "description": f"Retrieved status: {total}/{goal} ml ({percent}%). Formulating clear response."
        })

        if "how much more" in user_lower or "remaining" in user_lower or "need" in user_lower:
            if progress_res["goal_met"]:
                response = f"You have already met your daily goal! You've logged {total} ml today (target was {goal} ml)."
            else:
                response = f"You need {remaining} ml more to reach your {goal} ml goal today. You have had {total} ml so far ({percent}%)."
        else:
            response = (
                f"You have had {total} ml of water today. "
                f"Your daily goal is {goal} ml, leaving {remaining} ml remaining ({percent}% completed)."
            )

        return {"final_response": response, "trace": trace, "plan": step_1["description"]}

    def run(self, user_input: str) -> Dict[str, Any]:
        """Execute the agent for a user message, maintaining state across turns."""
        if not user_input or not user_input.strip():
            return {
                "response": "Please enter a message or specify the amount of water you drank.",
                "trace": [],
                "memory_state": self.memory.get_state(),
                "disclaimer": HEALTH_DISCLAIMER
            }

        # Check if Gemini API is configured for full LLM-driven tool calling
        has_timeline = bool(re.search(r"\b(yesterday|ereyesterday|tomorrow|tommorrow|overmorrow|today|last\s+day|day\s+before|day\s+after|next\s+week|next\s+month)\b|\bin\s+\d+\s+(day|days|week|weeks)\b|\b(?:on|for)?\s*\d{4}-\d{2}-\d{2}\b", user_input.lower()))
        if self.client and self.api_key and not has_timeline:
            memory_snapshot = copy.deepcopy(self.memory.__dict__)
            try:
                result = self._gemini_agent_loop(user_input)
            except Exception as e:
                self.memory.__dict__.clear()
                self.memory.__dict__.update(memory_snapshot)
                print(f"[Agent Warning] Gemini API execution failed: {e}. Using deterministic plan-act engine.")
                result = self._rule_based_agent_loop(user_input)
        else:
            result = self._rule_based_agent_loop(user_input)

        final_response = result["final_response"]
        trace = result["trace"]
        plan = result.get("plan", "Analyzed user hydration request and formulated step sequence.")

        # Persist this complete interaction turn in ConversationMemory
        self.memory.add_turn(
            user_message=user_input,
            plan=plan,
            steps=trace,
            final_response=final_response
        )

        return {
            "response": final_response,
            "trace": trace,
            "memory_state": self.memory.get_state(),
            "disclaimer": HEALTH_DISCLAIMER
        }

    def _gemini_agent_loop(self, user_input: str) -> Dict[str, Any]:
        """Multi-step agent loop using Gemini Function Calling."""
        trace: List[Dict[str, Any]] = []

        system_instruction = (
            "You are the Water Intake Coach AI Agent. Your role is to help users reach their daily "
            "water intake target. You have access to real tools: `log_water(ml)` and `get_progress()`. "
            "When a user mentions drinking water, you MUST call `log_water` with the amount. "
            "If they say yesterday or last day, pass intake_date as yesterday's ISO date; if they say tomorrow, pass tomorrow's ISO date. Non-today intake must not count toward today's total. "
            "After logging, check progress if needed to evaluate remaining water and goal completion. "
            "Be encouraging, gentle, and strictly avoid giving medical advice or urging dangerous over-hydration. "
            f"Current conversation context: Goal={self.memory.daily_goal_ml}ml, Today's Intake={self.memory.today_intake_ml}ml."
        )

        # Record initial planning step
        trace.append({
            "step_number": 1,
            "type": "plan",
            "description": f"Analyzed user prompt: '{user_input}'. Formulating tool selection strategy."
        })

        # Define tool functions for Gemini SDK
        tools_config = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="log_water",
                        description="Records water intake in milliliters (ml) and computes progress metrics.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "ml": types.Schema(
                                    type=types.Type.INTEGER,
                                    description="Amount of water in milliliters, e.g., 250, 500."
                                ),
                                "intake_date": types.Schema(
                                    type=types.Type.STRING,
                                    description="ISO date for when the water was consumed; omit for today."
                                )
                            },
                            required=["ml"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="get_progress",
                        description="Retrieves current water consumption progress, remaining ml, and target status.",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={}
                        )
                    ),
                    types.FunctionDeclaration(
                        name="set_daily_goal",
                        description="Updates the user daily water goal in milliliters (default 2500 ml).",
                        parameters=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "ml": types.Schema(
                                    type=types.Type.INTEGER,
                                    description="New target in ml."
                                )
                            },
                            required=["ml"]
                        )
                    )
                ]
            )
        ]

        messages = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_input)]
            )
        ]

        step_count = 1
        final_response_text = ""

        # Plan-Act Loop (with max step protection)
        while step_count < MAX_AGENT_STEPS:
            step_count += 1

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools_config,
                    temperature=0.2
                )
            )

            # Check if model requested tool call(s)
            function_calls = response.function_calls
            if function_calls:
                for fc in function_calls:
                    tool_name = fc.name
                    tool_args = fc.args or {}

                    trace.append({
                        "step_number": len(trace) + 1,
                        "type": "tool_call",
                        "tool": tool_name,
                        "arguments": tool_args
                    })

                    # Act: execute tool in Python
                    tool_result = self.execute_tool(tool_name, tool_args)

                    trace.append({
                        "step_number": len(trace) + 1,
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": tool_result
                    })

                    trace.append({
                        "step_number": len(trace) + 1,
                        "type": "observation",
                        "description": f"Tool '{tool_name}' output: {json.dumps(tool_result)}"
                    })

                    # Append model turn and tool response turn to context
                    messages.append(response.candidates[0].content)
                    messages.append(
                        types.Content(
                            role="tool",
                            parts=[
                                types.Part.from_function_response(
                                    name=tool_name,
                                    response={"result": tool_result}
                                )
                            ]
                        )
                    )
            else:
                # No more tools requested; final response generated
                final_response_text = response.text or ""
                trace.append({
                    "step_number": len(trace) + 1,
                    "type": "decision",
                    "description": "All necessary tool actions completed. Formulated final response."
                })
                break

        if not final_response_text:
            # Fallback if loop ended via max steps
            state = self.memory.get_state()
            final_response_text = (
                f"You have had {state['today_intake_ml']} ml today out of your {state['daily_goal_ml']} ml target "
                f"({state['remaining_ml']} ml remaining, {state['progress_percent']}%)."
            )

        return {
            "final_response": final_response_text,
            "trace": trace,
            "plan": trace[0]["description"] if trace else "Plan formulated"
        }
