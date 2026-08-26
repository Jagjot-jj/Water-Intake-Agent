"""Configuration settings for the Water Intake Coach AI Agent."""
import os
from dotenv import load_dotenv

load_dotenv()

# Default daily hydration target in milliliters (ml)
DEFAULT_DAILY_GOAL_ML = 2500

# Safety & Health Disclaimer required for university demonstration
HEALTH_DISCLAIMER = (
    "This project provides simple hydration tracking and reminders for "
    "demonstration purposes. It does not provide medical advice. "
    "Individual hydration needs vary."
)

# Gemini Model configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Maximum execution steps per turn in the Plan-Act agent loop to prevent infinite cycling
MAX_AGENT_STEPS = 6
