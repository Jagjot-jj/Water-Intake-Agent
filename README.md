# 💧 Water Intake Coach (T16 - Health)

The **Water Intake Coach** is an autonomous AI agent designed to help users reach their daily hydration target through a multi-step plan-act loop rather than acting as a simple conversational chatbot. The system integrates two core Python tools: `log_water(ml)` (which validates inputs, enforces positive values, increments today's intake, and computes current metrics) and `get_progress()` (which queries the active state to retrieve total intake, remaining volume, completion percentage, and goal status). The agent is supported by a stateful `ConversationMemory` module that maintains user goals, logged consumption events, and multi-turn interaction traces across the entire session so the agent seamlessly remembers prior water intake.

Rather than producing immediate static text, the agent executes an autonomous multi-step decision loop: upon receiving a user goal, it analyzes intent, formulates an action plan, selects and runs the appropriate tool (such as logging water), observes the structured tool results, and evaluates whether secondary actions (such as fetching refreshed progress metrics or adjusting recommendations) are required before generating a gentle, non-medical final response.

During development, an initial limitation occurred where the agent emitted a final response immediately after calling `log_water(ml)` without refreshing cumulative statistics, causing it to miscalculate remaining amounts when multiple complex user intents occurred in a single turn. This was resolved by restructuring the plan-act loop to execute a subsequent `get_progress()` step whenever water is logged, passing structured observation metrics back to the decision engine so all responses are strictly grounded in up-to-date state.

---

### Project Structure
```
water-intake-coach/
│
├── README.md               # Assignment documentation & specifications
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variable template for GEMINI_API_KEY
├── config.py               # Constants, defaults (2500ml), and health disclaimer
├── memory.py               # ConversationMemory class for multi-turn persistence
├── tools.py                # Implementation of log_water(), get_progress(), set_daily_goal()
├── agent.py                # WaterIntakeAgent with Plan-Act-Observe-Decide loop
├── app.py                  # Interactive Streamlit Web UI
│
├── notebook/
│   └── water_intake_coach_demo.ipynb  # Executable 3-scenario demo with traces
│
└── tests/
    └── test_tools.py       # 9 comprehensive pytest test cases
```

### Quick Start Guide

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Key (Optional for Gemini function calling)**:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY inside .env
   ```

3. **Run Unit Tests**:
   ```bash
   pytest tests/test_tools.py -v
   ```

4. **Launch Streamlit Dashboard**:
   ```bash
   streamlit run app.py
   ```

5. **Run Jupyter Notebook Demo**:
   ```bash
   jupyter notebook notebook/water_intake_coach_demo.ipynb
   ```

### Health Disclaimer
*This project provides simple hydration tracking and reminders for demonstration purposes. It does not provide medical advice. Individual hydration needs vary.*
