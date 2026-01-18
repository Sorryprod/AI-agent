"""
AI Agent: Final Polish
- Smart Start (пропуск анализа пустой страницы)
- Safe Browser Exit (обработка закрытия вкладки)
"""
import asyncio
import json
import uuid
from typing import Callable, List, Dict, Any
from google.genai import Client as GeminiClient, types
from openai import AsyncOpenAI

from .browser_controller import BrowserController
from .page_analyzer import PageAnalyzer
from .context_manager import ContextManager
from .tools import TOOLS
from config import GOOGLE_API_KEY, GOOGLE_MODEL, OPENAI_API_KEY, OPENAI_MODEL

SYSTEM_INSTRUCTION = """You are an autonomous browser agent.
IMPORTANT RULES:
1. REPLY IN RUSSIAN.
2. THOUGHTS: Do NOT ask questions. State facts. 
   BAD: "Should I click?" 
   GOOD: "I see the button. I will click it."
3. NAVIGATION: Use `get_page_content` to find element IDs.
4. INPUT: Find the input ID -> `type_text` -> `press_key('Enter')`.
5. COMPLETION: When the goal is achieved (e.g. item in cart), DO NOT just say "Done". You MUST call the `report_result` tool immediately to finish the task.
"""

class AIAgent:
    def __init__(self, browser: BrowserController, log_callback: Callable = None):
        self.browser = browser
        self.context = ContextManager()
        self.log = log_callback
        self.running = False
        self.paused = False
        
        self.gemini = GeminiClient(api_key=GOOGLE_API_KEY, http_options={'timeout': 120.0})
        self.openai = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
        
        self.tools_gemini = self._create_gemini_tools()
        self.tools_openai = self._create_openai_tools()
        self.provider = "gemini" 

    async def execute_task(self, task: str):
        self.context.set_task(task)
        self.running = True
        self.paused = False
        self.provider = "gemini"

        await self.log("system", f"🚀 Задача: {task}")

        # --- SMART START: Проверка URL ---
        try:
            current_url = self.browser.page.url
            if current_url == "about:blank":
                # Если страница пустая, не тратим время на анализ, а сразу даем контекст
                initial_msg = f"Task: {task}\nBrowser is open at 'about:blank'. START BY NAVIGATING to the required site."
            else:
                initial_msg = f"Task: {task}\nStart by analyzing the current page."
        except:
            initial_msg = f"Task: {task}\nStart."

        history = [{"role": "user", "content": initial_msg}]
        last_thought = ""
        
        iteration = 0
        while self.running and iteration < 60:
            
            # --- SAFE EXIT: Проверка жизни браузера ---
            if not self.browser.page or self.browser.page.is_closed():
                await self.log("error", "Вкладка браузера закрыта. Остановка.")
                self.running = False
                break

            while self.paused:
                await asyncio.sleep(0.5)
                if not self.running: break
            if not self.running: break

            iteration += 1
            history = self._trim_history(history)

            try:
                response = await self._call_llm_with_fallback(history)
                if not response: 
                    await asyncio.sleep(1)
                    continue

                content = response.get("content")
                tool_calls = response.get("tool_calls", [])

                if content:
                    clean_content = content.strip()
                    if clean_content and clean_content != last_thought:
                        await self.log("thought", clean_content)
                        history.append({"role": "assistant", "content": clean_content})
                        last_thought = clean_content
                        await asyncio.sleep(min(len(clean_content) * 0.05, 3.0))
                        
                        # --- ЭВРИСТИКА ЗАВЕРШЕНИЯ ---
                        # Если агент говорит, что все сделал, но не вызывает инструмент
                        lower_content = clean_content.lower()
                        if "успешно" in lower_content and ("добавлен" in lower_content or "выполнен" in lower_content):
                            # Добавляем подсказку от пользователя
                            history.append({"role": "user", "content": "Great! Call `report_result` now."})
                            continue

                if not tool_calls and not content:
                    history.append({"role": "user", "content": "Proceed."})
                    continue

                if tool_calls:
                    msg = {"role": "assistant", "tool_calls": tool_calls}
                    if content: msg["content"] = content
                    if history[-1] != msg: history.append(msg)

                for tool in tool_calls:
                    while self.paused: await asyncio.sleep(0.5)
                    if not self.running: break

                    func_name = tool['name']
                    args = tool['args']
                    call_id = tool['id']

                    await self.log("tool", f"🔧 {func_name}: {args}")

                    # Вторичная проверка перед действием
                    if not self.browser.page or self.browser.page.is_closed():
                        await self.log("error", "Браузер закрыт.")
                        self.running = False
                        break

                    result = await self._execute_tool(func_name, args)
                    
                    if func_name == "report_result":
                        self.running = False
                        await self.log("success", result.get('result', 'Готово'))
                        return

                    history.append({
                        "role": "tool", "tool_call_id": call_id, "name": func_name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

            except Exception as e:
                if not self.running: return
                error_msg = str(e)
                
                # Если браузер закрыли во время запроса
                if "Target closed" in error_msg or "context was destroyed" in error_msg:
                    await self.log("error", "Браузер был закрыт.")
                    self.running = False
                    return

                print(f"Error: {e}")
                await asyncio.sleep(2)

    def _trim_history(self, history):
        if len(history) > 12: return [history[0]] + history[-10:]
        return history

    async def _call_llm_with_fallback(self, history):
        if self.provider == "openai" and self.openai:
            return await self._call_openai(history)
        try:
            return await self._call_gemini(history)
        except Exception as e:
            if not self.running: return {}
            if self.openai:
                self.provider = "openai"
                return await self._call_openai(history)
            raise e

    # --- ADAPTERS ---
    async def _call_gemini(self, history):
        gemini_hist = []
        for msg in history:
            parts = []
            if msg.get('content'): parts.append(types.Part(text=str(msg['content'])))
            if msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    parts.append(types.Part(function_call=types.FunctionCall(name=tc['name'], args=tc['args'])))
            if msg.get('role') == 'tool':
                parts.append(types.Part(function_response=types.FunctionResponse(name=msg.get('name', 'unknown'), response=json.loads(msg['content']))))
            role = "model" if msg['role'] == "assistant" else "user"
            if msg['role'] == 'tool': role = 'user'
            gemini_hist.append(types.Content(role=role, parts=parts))

        response = self.gemini.models.generate_content(
            model=GOOGLE_MODEL, contents=gemini_hist,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, tools=self.tools_gemini, temperature=0.5)
        )
        cand = response.candidates[0].content
        content_txt = "".join([p.text for p in cand.parts if p.text])
        tool_calls = []
        for p in cand.parts:
            if p.function_call:
                tool_calls.append({"id": str(uuid.uuid4()), "name": p.function_call.name, "args": dict(p.function_call.args)})
        return {"content": content_txt, "tool_calls": tool_calls}

    async def _call_openai(self, history):
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}] 
        clean = []
        pending = set()
        for msg in history:
            if msg['role'] == 'system': continue
            if msg.get('tool_calls'):
                for t in msg['tool_calls']: pending.add(t['id'])
                clean.append(msg)
            elif msg['role'] == 'tool':
                if msg.get('tool_call_id') in pending: clean.append(msg)
            else:
                clean.append(msg)
        
        for msg in clean:
            new_msg = {"role": msg["role"], "content": msg.get("content")}
            if msg.get("tool_calls"):
                new_msg["tool_calls"] = [{"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}} for tc in msg["tool_calls"]]
            if msg["role"] == "tool":
                new_msg["tool_call_id"] = msg.get("tool_call_id")
            messages.append(new_msg)

        response = await self.openai.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, tools=self.tools_openai, tool_choice="auto"
        )
        res_msg = response.choices[0].message
        tool_calls = []
        if res_msg.tool_calls:
            for tc in res_msg.tool_calls:
                tool_calls.append({"id": tc.id, "name": tc.function.name, "args": json.loads(tc.function.arguments)})
        return {"content": res_msg.content, "tool_calls": tool_calls}

    # --- TOOLS SETUP ---
    def _create_gemini_tools(self):
        tools = []
        for t in TOOLS:
            props = {k: types.Schema(type=types.Type.STRING) for k in t["parameters"]["properties"]}
            tools.append(types.FunctionDeclaration(name=t["name"], description=t["description"], parameters=types.Schema(type=types.Type.OBJECT, properties=props)))
        return [types.Tool(function_declarations=tools)]

    def _create_openai_tools(self):
        return [{"type": "function", "function": t} for t in TOOLS]

    # --- EXECUTION ---
    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        try:
            # Проверка перед выполнением
            if not self.browser.page or self.browser.page.is_closed():
                return {"success": False, "error": "Browser closed"}

            if tool_name == "navigate": return await self.browser.navigate(params.get("url", ""))
            elif tool_name == "click": return await self.browser.click(params.get("selector", ""))
            elif tool_name == "type_text": return await self.browser.type_text(params.get("selector", ""), params.get("text", ""))
            elif tool_name == "fill": return await self.browser.fill(params.get("selector", ""), params.get("text", ""))
            elif tool_name == "press_key": return await self.browser.press_key(params.get("key", "Enter"))
            elif tool_name == "scroll": return await self.browser.scroll(params.get("direction", "down"))
            elif tool_name == "get_page_content":
                if not self.browser.page: return {"success": False, "error": "No browser"}
                analyzer = PageAnalyzer(self.browser.page)
                return {"success": True, "content": await analyzer.get_compact_state()}
            elif tool_name == "go_back": return await self.browser.go_back()
            elif tool_name == "wait": return await self.browser.wait(min(float(params.get("seconds", 1)), 10))
            elif tool_name == "hover": return await self.browser.hover(params.get("selector", ""))
            elif tool_name == "ask_user": return {"success": True, "error": "Input not supported"}
            elif tool_name == "request_confirmation": return {"success": True, "approved": True}
            elif tool_name == "save_finding": return {"success": True}
            elif tool_name == "report_result": return {"success": params.get("success", True), "result": params.get("result", "")}
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}