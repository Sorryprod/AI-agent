"""
AI Agent (Web Version)
Отправляет логи через колбэк, а не print.
"""
import asyncio
import json
from typing import Callable, List
from google.genai import Client, types

from .browser_controller import BrowserController
from .page_analyzer import PageAnalyzer
from .context_manager import ContextManager
from .tools import TOOLS
from config import GOOGLE_API_KEY, MODEL

SYSTEM_INSTRUCTION = """You are a fast AI browser agent.
RULES:
1. Use get_page_content ONCE at start.
2. Prefer text= clicking.
3. If element missing, scroll.
4. Call report_result when done.
"""

class AIAgent:
    def __init__(self, browser: BrowserController, log_callback: Callable = None):
        self.browser = browser
        self.client = Client(api_key=GOOGLE_API_KEY)
        self.tools = self._create_tools()
        self.context = ContextManager()
        self.log = log_callback or print # Если веб не подключен, пишем в консоль
        self.running = False
        self.paused = False # Флаг паузы

    def _create_tools(self) -> List[types.Tool]:
        # (Код создания инструментов тот же, сокращен для краткости)
        tools_list = []
        for tool_def in TOOLS:
            properties = {}
            for prop_name, prop_schema in tool_def["parameters"]["properties"].items():
                properties[prop_name] = types.Schema(type=types.Type.STRING) # Упростили типы для надежности
            parameters = types.Schema(type=types.Type.OBJECT, properties=properties)
            func = types.FunctionDeclaration(name=tool_def["name"], description=tool_def["description"], parameters=parameters)
            tools_list.append(func)
        return [types.Tool(function_declarations=tools_list)]

    async def execute_task(self, task: str):
        self.context.set_task(task)
        self.running = True
        self.paused = False
        
        
        await self.log("system", f"🚀 Запускаю задачу: {task}")
        
        chat_history = [types.Content(role="user", parts=[types.Part(text=f"Task: {task}")])]
        
        iteration = 0
        try:
            while self.running and iteration < 50:
                iteration += 1
                while self.paused:
                    # Агент просто спит и ждет флага False
                    await asyncio.sleep(0.5)
                    if not self.running: break # Если нажали стоп во время паузы
                
                if not self.running: break # Выход из цикла
                
                # Запрос к AI
                try:
                    response = self.client.models.generate_content(
                        model=MODEL,
                        contents=chat_history,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            tools=self.tools,
                            temperature=0.4,
                            max_output_tokens=500
                        )
                    )
                except Exception as e:
                    await self.log("error", f"Ошибка сети API: {e}. Пробую снова...")
                    await asyncio.sleep(2)
                    continue

                if not response.candidates:
                    break

                model_content = response.candidates[0].content
                chat_history.append(model_content)

                function_calls = []
                for part in model_content.parts:
                    if part.text:
                        await self.log("thought", part.text)
                    if part.function_call:
                        function_calls.append(part.function_call)

                if not function_calls:
                    chat_history.append(types.Content(role="user", parts=[types.Part(text="Continue.")]))
                    continue

                function_response_parts = []

                for func_call in function_calls:
                    func_name = func_call.name
                    func_args = dict(func_call.args) if func_call.args else {}

                    await self.log("tool", f"🔧 {func_name}: {func_args}")
                    
                    # Выполнение
                    result = await self._execute_tool(func_name, func_args)
                    
                    status = "✅" if result.get("success") else "❌"
                    msg = str(result.get('result') or result.get('message') or result.get('error') or 'Done')
                    await self.log("result", f"   {status} {msg}")

                    if func_name == "report_result":
                        self.running = False
                        success = result.get("success", True)
                        if success:
                            await self.log("success", f"🏁 ГОТОВО: {result.get('result')}")
                        else:
                            await self.log("error", f"⛔ НЕУДАЧА: {result.get('result')}")
                        return

                    function_response_parts.append(types.Part(
                        function_response=types.FunctionResponse(name=func_name, response=result)
                    ))

                if function_response_parts:
                    chat_history.append(types.Content(role="user", parts=function_response_parts))

        except Exception as e:
            await self.log("error", f"Критическая ошибка: {str(e)}")
        finally:
            self.running = False
            await self.log("system", "⏹️ Агент остановлен")

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        # (Код инструментов тот же, что и в BrowserController)
        # Просто вызываем методы browser
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
            elif tool_name == "wait": return await self.browser.wait(min(float(params.get("seconds", 1)), 5))
            elif tool_name == "request_confirmation": return {"success": True, "approved": True} # Авто-аппрув для веба пока
            elif tool_name == "report_result": 
                return {"success": params.get("success", True), "result": params.get("result", "")}
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}