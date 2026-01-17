import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from agent.browser_controller import BrowserController
from agent.ai_agent import AIAgent
from config import USER_DATA_DIR, HEADLESS

app = FastAPI()

# Глобальное состояние
browser = None
current_agent = None

@app.on_event("startup")
async def startup_event():
    global browser
    # Инициализируем браузер один раз при старте сервера
    browser = BrowserController(user_data_dir=USER_DATA_DIR, headless=HEADLESS)
    await browser.start()
    print("Browser started and ready")

@app.on_event("shutdown")
async def shutdown_event():
    if browser:
        await browser.stop()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    global current_agent
    
    async def log_to_web(type: str, message: str):
        try: await websocket.send_json({"type": type, "message": message})
        except: pass

    if current_agent and current_agent.running:
        current_agent.log = log_to_web

    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            
            if command == "get_status":
                is_running = current_agent is not None and current_agent.running
                await websocket.send_json({"type": "status", "is_running": is_running})

            elif command == "start":
                task = data.get("task")
                if current_agent and current_agent.running:
                    await log_to_web("error", "Задача уже выполняется!")
                    continue
                current_agent = AIAgent(browser, log_callback=log_to_web)
                asyncio.create_task(current_agent.execute_task(task))
                
            elif command == "stop":
                if current_agent:
                    current_agent.running = False
                    await log_to_web("error", "Остановлено пользователем")

            # --- НОВЫЕ КОМАНДЫ ---
            elif command == "pause":
                if current_agent:
                    current_agent.paused = True
            
            elif command == "resume":
                if current_agent:
                    current_agent.paused = False

    except Exception as e:
        print(f"WebSocket disconnected: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)