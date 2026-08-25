"""Streamlit Web Interface for the Water Intake Coach AI Agent.

Run with:
    streamlit run app.py
"""
import streamlit as st
import json
from agent import WaterIntakeAgent
from config import DEFAULT_DAILY_GOAL_ML, HEALTH_DISCLAIMER
from memory import ConversationMemory

# Page configuration
st.set_page_config(
    page_title="💧 Water Intake Coach",
    page_icon="💧",
    layout="wide"
)

# Initialize session state for memory and agent
if "memory" not in st.session_state:
    st.session_state.memory = ConversationMemory(daily_goal_ml=DEFAULT_DAILY_GOAL_ML)

if "agent" not in st.session_state:
    st.session_state.agent = WaterIntakeAgent(memory=st.session_state.memory)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "latest_trace" not in st.session_state:
    st.session_state.latest_trace = []

# Header
st.title("💧 Water Intake Coach")
st.caption("Course Project: T16. Water Intake Coach [Health] — Plan-Act Agent with Multi-Step Loop & Memory")

# Health Disclaimer
st.info(f"ℹ️ **Health Disclaimer**: {HEALTH_DISCLAIMER}")

# Fetch current state from memory
state = st.session_state.memory.get_state()

# Top Dashboard Metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎯 Daily Goal", f"{state['daily_goal_ml']} ml")
with col2:
    st.metric("💧 Today's Intake", f"{state['today_intake_ml']} ml")
with col3:
    st.metric("⏳ Remaining", f"{state['remaining_ml']} ml")
with col4:
    progress_val = min(1.0, state['progress_percent'] / 100.0)
    st.metric("📊 Progress", f"{state['progress_percent']}%")

st.progress(progress_val)

if state['goal_exceeded']:
    st.success(f"🎉 Fantastic! Daily goal exceeded ({state['today_intake_ml']}/{state['daily_goal_ml']} ml). Stay balanced!")
elif state['goal_met']:
    st.success(f"🏆 Goal reached! You have consumed {state['today_intake_ml']} ml today.")

st.divider()

# Layout: Left column is Chat & Agent Loop, Right column is Memory & Trace Inspector
chat_col, inspector_col = st.columns([3, 2])

with chat_col:
    st.subheader("💬 Conversation with AI Agent")

    # Quick scenario buttons for professor / evaluator
    st.write("**Quick Scenario Inputs:**")
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
    quick_input = None
    if btn_col1.button("Scenario 1: Log 500 ml"):
        quick_input = "I just drank 500 ml of water."
    if btn_col2.button("Scenario 2: Add 300 ml"):
        quick_input = "I drank another 300 ml."
    if btn_col3.button("Check Remaining"):
        quick_input = "How much more do I need today?"
    if btn_col4.button("Scenario 3: Reach Goal"):
        quick_input = "I drank 1700 ml of water."

    # Render previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # User input
    user_input = st.chat_input("Tell the agent what you drank or ask about your progress...")
    if quick_input:
        user_input = quick_input

    if user_input:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        # Run agent plan-act loop
        with st.spinner("Agent planning and executing tools..."):
            result = st.session_state.agent.run(user_input)

        response_text = result["response"]
        st.session_state.latest_trace = result["trace"]
        st.session_state.messages.append({"role": "assistant", "content": response_text})

        with st.chat_message("assistant"):
            st.write(response_text)

        st.rerun()

with inspector_col:
    st.subheader("🔍 Agentic Trace & State Inspector")
    tab1, tab2, tab3 = st.tabs(["⚡ Latest Multi-Step Trace", "🧠 Conversation Memory", "⚙️ Goal Control"])

    with tab1:
        if st.session_state.latest_trace:
            st.write("**Plan-Act-Observe-Decide Trace:**")
            for step in st.session_state.latest_trace:
                step_type = step.get("type", "step")
                num = step.get("step_number", "")

                if step_type == "plan":
                    st.markdown(f"**[Step {num}: PLAN]** {step.get('description', '')}")
                elif step_type == "tool_call":
                    st.markdown(f"🔧 **[Step {num}: TOOL CALL]** `{step.get('tool')}({json.dumps(step.get('arguments', {}))})`")
                elif step_type == "tool_result":
                    st.markdown(f"📥 **[Step {num}: TOOL RESULT]**")
                    st.json(step.get("result", {}))
                elif step_type == "observation":
                    st.markdown(f"👁️ **[Step {num}: OBSERVATION]** {step.get('description', '')}")
                elif step_type == "decision":
                    st.markdown(f"💡 **[Step {num}: DECISION]** {step.get('description', '')}")
        else:
            st.caption("No agent trace yet. Send a message to see the multi-step loop in action!")

    with tab2:
        st.write("**Real Python `ConversationMemory` State:**")
        mem_dump = st.session_state.memory.to_dict()
        st.json(mem_dump)

        if st.button("🗑️ Reset Memory Session"):
            st.session_state.memory.reset()
            st.session_state.messages = []
            st.session_state.latest_trace = []
            st.success("Memory reset successfully.")
            st.rerun()

    with tab3:
        new_goal = st.number_input("Update Daily Goal (ml):", min_value=500, max_value=5000, value=state['daily_goal_ml'], step=250)
        if st.button("Apply New Goal"):
            st.session_state.memory.set_goal(int(new_goal))
            st.success(f"Goal updated to {new_goal} ml.")
            st.rerun()
