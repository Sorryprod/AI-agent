"""
AI Agent: Hybrid (Google Gemini + OpenAI Fallback)
Исправлено: Санитайзер истории для устранения ошибки 'Invalid parameter: messages with role tool'.
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
IMPORTANT:
1. Always analyze page first.
2. The page analysis gives elements IDs like `[12] <button> ...`.
3. TO CLICK, USE THE ID: `click(selector='[12]')`. This is the most reliable way.
4. If ID is missing, use text or selector.
5. If you see `{Context: Burger}`, the button belongs to "Burger".
6. Reply in Russian.
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

        history = [{"role": "user", "content": f"Task: {task}\nStart by analyzing the page."}]
        
        iteration = 0
        
        while self.running and iteration < 60:
            while self.paused:
                await asyncio.sleep(0.5)
                if not self.running: break
            if not self.running: break

            iteration += 1

            try:
                response = await self._call_llm_with_fallback(history)
                
                content = response.get("content")
                tool_calls = response.get("tool_calls", [])

                # Формируем сообщение ассистента
                assistant_msg = {"role": "assistant"}
                if content: assistant_msg["content"] = content
                if tool_calls: assistant_msg["tool_calls"] = tool_calls
                
                # Добавляем только если есть контент или вызовы
                if content or tool_calls:
                    history.append(assistant_msg)
                else:
                    history.append({"role": "user", "content": "Proceed."})
                    continue

                for tool in tool_calls:
                    if not self.running: break

                    func_name = tool['name']
                    args = tool['args']
                    call_id = tool['id']

                    await self.log("tool", f"🔧 {func_name}: {args}")

                    result = await self._execute_tool(func_name, args)
                    
                    if func_name == "report_result":
                        self.running = False
                        await self.log("success", result.get('result', 'Готово'))
                        return

                    history.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": func_name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

            except Exception as e:
                error_msg = str(e)
                print(f"Loop Error: {error_msg}")
                
                if "timed out" in error_msg:
                    await asyncio.sleep(1)
                    continue

                if self.provider == "openai":
                    await self.log("error", f"Ошибка OpenAI: {error_msg[:100]}...")
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(1)

    async def _call_llm_with_fallback(self, history):
        if self.provider == "openai" and self.openai:
            return await self._call_openai(history)

        try:
            return await self._call_gemini(history)
        except Exception as e:
            print(f"Gemini Error: {e}")
            if self.openai:
                # await self.log("thought", "⚠️ Сбой Gemini. Переключаюсь на GPT-4o...")
                self.provider = "openai"
                return await self._call_openai(history)
            else:
                raise e

    # --- ADAPTERS ---
    async def _call_gemini(self, history):
        gemini_hist = []
        for msg in history:
            parts = []
            
            if msg.get('content'):
                parts.append(types.Part(text=msg['content']))
            
            if msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    parts.append(types.Part(function_call=types.FunctionCall(name=tc['name'], args=tc['args'])))
            
            if msg.get('role') == 'tool':
                parts.append(types.Part(function_response=types.FunctionResponse(name=msg.get('name'), response=json.loads(msg['content']))))
            
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
        # 1. Санитизация истории (чистим от битых сообщений)
        clean_history = self._sanitize_history_for_openai(history)
        
        # 2. Добавляем системный промпт
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}] + clean_history

        response = await self.openai.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, tools=self.tools_openai, tool_choice="auto"
        )
        res_msg = response.choices[0].message
        tool_calls = []
        if res_msg.tool_calls:
            for tc in res_msg.tool_calls:
                tool_calls.append({"id": tc.id, "name": tc.function.name, "args": json.loads(tc.function.arguments)})
        return {"content": res_msg.content, "tool_calls": tool_calls}

    def _sanitize_history_for_openai(self, history):
        """
        Проверяет и исправляет историю для OpenAI:
        1. Каждое сообщение tool должно иметь предшествующий tool_calls с совпадающим ID.
        2. Форматирует tool_calls в правильную структуру.
        """
        clean = []
        # Словарь ожидающих вызовов: id -> msg
        pending_tool_calls = {} 

        for msg in history:
            new_msg = {"role": msg["role"], "content": msg.get("content")}
            
            # Если это ассистент с вызовами
            if msg.get("tool_calls"):
                openai_tools = []
                for tc in msg["tool_calls"]:
                    # Сохраняем ID, чтобы проверить ответ
                    pending_tool_calls[tc["id"]] = True
                    
                    openai_tools.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"])
                        }
                    })
                new_msg["tool_calls"] = openai_tools
                clean.append(new_msg)
                continue

            # Если это ответ инструмента
            if msg["role"] == "tool":
                call_id = msg.get("tool_call_id")
                # Если такого вызова не было в истории - ПРОПУСКАЕМ сообщение (удаляем сироту)
                if not call_id or call_id not in pending_tool_calls:
                    # print(f"Skipping orphan tool message: {call_id}")
                    continue
                
                # Помечаем как обработанный (опционально, OpenAI разрешает отвечать не по порядку, но важно чтобы ID был)
                new_msg["tool_call_id"] = call_id
                clean.append(new_msg)
                continue

            # Обычное сообщение пользователя
            clean.append(new_msg)
            
        return clean

    # --- TOOLS SETUP & EXECUTION ---
    def _create_gemini_tools(self):
        tools = []
        for t in TOOLS:
            props = {k: types.Schema(type=types.Type.STRING) for k in t["parameters"]["properties"]}
            tools.append(types.FunctionDeclaration(name=t["name"], description=t["description"], parameters=types.Schema(type=types.Type.OBJECT, properties=props)))
        return [types.Tool(function_declarations=tools)]

    def _create_openai_tools(self):
        return [{"type": "function", "function": t} for t in TOOLS]

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        try:
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
            elif tool_name == "ask_user": return {"success": True, "error": "User input not available"}
            elif tool_name == "request_confirmation": return {"success": True, "approved": True}
            elif tool_name == "save_finding": return {"success": True}
            elif tool_name == "report_result": return {"success": params.get("success", True), "result": params.get("result", "")}
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}