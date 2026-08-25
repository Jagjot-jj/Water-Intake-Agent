"""Command-Line Interface for the Water Intake Coach Agent.

Usage:
    python main.py
"""
import sys
import json
from agent import WaterIntakeAgent
from config import HEALTH_DISCLAIMER
from memory import ConversationMemory


def main():
    print("=" * 70)
    print("💧 Water Intake Coach — Autonomous AI Agent CLI")
    print(f"ℹ️  {HEALTH_DISCLAIMER}")
    print("=" * 70)
    print("Commands:")
    print("  Type your message (e.g., 'I drank 500 ml', 'How much more do I need?')")
    print("  'trace'    - View the complete trace of the last turn")
    print("  'memory'   - Inspect raw conversation memory state")
    print("  'reset'    - Reset conversation memory")
    print("  'scenario' - Run automatic 3-scenario course demonstration")
    print("  'exit'     - Quit the program")
    print("=" * 70)

    memory = ConversationMemory()
    agent = WaterIntakeAgent(memory=memory)
    last_trace = []

    while True:
        try:
            user_input = input("\n👤 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Water Intake Coach. Stay hydrated!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ["exit", "quit", "q"]:
            print("Exiting Water Intake Coach. Goodbye!")
            break
        elif cmd == "trace":
            print("\n--- LAST AGENT TRACE ---")
            print(json.dumps(last_trace, indent=2))
            continue
        elif cmd == "memory":
            print("\n--- CONVERSATION MEMORY DUMP ---")
            print(json.dumps(memory.to_dict(), indent=2))
            continue
        elif cmd == "reset":
            memory.reset()
            last_trace = []
            print("🔄 Memory has been reset to default state (0 ml / 2500 ml).")
            continue
        elif cmd == "scenario":
            print("\n🚀 Running Course Demo Scenarios...\n")
            scenarios = [
                "I just drank 500 ml of water.",
                "I drank another 300 ml.",
                "How much have I had today?",
                "I drank 1700 ml from my water bottle."
            ]
            for s in scenarios:
                print(f"👤 USER: {s}")
                res = agent.run(s)
                print(f"🤖 AGENT: {res['response']}")
                print(f"📊 Progress: {res['memory_state']['today_intake_ml']}/{res['memory_state']['daily_goal_ml']} ml ({res['memory_state']['progress_percent']}%)")
                print("-" * 50)
            continue

        result = agent.run(user_input)
        last_trace = result["trace"]

        print(f"\n🤖 Coach: {result['response']}")
        state = result["memory_state"]
        print(f"📊 [Status: {state['today_intake_ml']}/{state['daily_goal_ml']} ml | Remaining: {state['remaining_ml']} ml | {state['progress_percent']}%]")


if __name__ == "__main__":
    main()
