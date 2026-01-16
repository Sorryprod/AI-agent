import os
from dotenv import load_dotenv

load_dotenv()

# Google Gemini Configuration (New SDK)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL = "gemini-2.5-flash-lite"  # Новейшая быстрая модель

HEADLESS = False
USER_DATA_DIR = "./browser_session"
VIEWPORT = {"width": 1280, "height": 900}