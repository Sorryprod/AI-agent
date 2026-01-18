import os
from dotenv import load_dotenv

load_dotenv()

# Google Gemini Configuration (New SDK)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL = "gemini-2.5-flash-lite"  # Новейшая быстрая модель


# OpenAI (Запасной - Платный, но надежный)
# Если ключа нет, агент просто сообщит об ошибке
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o" 

HEADLESS = False
USER_DATA_DIR = "./browser_session"
VIEWPORT = {"width": 1280, "height": 900}

DEBUG_MODE = True