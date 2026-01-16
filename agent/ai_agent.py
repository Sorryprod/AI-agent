"""
AI Agent с использованием Google Gemini (новый SDK google-genai)
Версия: Clean & Stable (Ручные ретраи, без http_options)
"""
import asyncio
import time
import json
from typing import Callable, List
from google.genai import Client, types

from .browser_controller import BrowserController
from .page_analyzer import PageAnalyzer
from .context_manager import ContextManager
from .tools import TOOLS
from config import GOOGLE_API_KEY, MODEL


SYSTEM_INSTRUCTION = """You are an autonomous AI browser agent.

## Rules
1. ALWAYS start with get_page_content.
2. Use tool calls to interact with browser.
3. If action fails, analyze error and try different approach.
4. When task complete, call report_result.

## Tools
- get_page_content: Use often to see page state.
- click: Click element.
- fill/type_text: Input text.
- press_key: Press Enter, etc.
- scroll: Scroll page.
- navigate: Go to URL.
"""


class AIAgent:
    def __init__(
        self,
        browser: BrowserController,
        on_user_question: Callable[[str], str] = None,
        on_confirmation: Callable[[str], bool] = None
    ):
        self.browser = browser
        
        # УБРАЛИ http_options, чтобы не было ошибки "deadline 1s"
        # Используем настройки по умолчанию
        self.client = Client(api_key=GOOGLE_API_KEY)
        
        self.tools = self._create_tools()
        self.context = ContextManager()
        self.on_user_question = on_user_question or self._default_question
        self.on_confirmation = on_confirmation or self._default_confirmation
        self.running = False

    def _create_tools(self) -> List[types.Tool]:
        tools_list = []
        for tool_def in TOOLS:
            properties = {}
            for prop_name, prop_schema in tool_def["parameters"]["properties"].items():
                properties[prop_name] = types.Schema(
                    type=self._get_schema_type(prop_schema.get("type", "string")),
                    description=prop_schema.get("description", "")
                )
            parameters = types.Schema(
                type=types.Type.OBJECT,
                properties=properties,
                required=tool_def["parameters"].get("required", [])
            )
            func = types.FunctionDeclaration(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=parameters
            )
            tools_list.append(func)
        return [types.Tool(function_declarations=tools_list)]
    
    @staticmethod
    def _get_schema_type(type_str: str) -> types.Type:
        type_map = {
            "string": types.Type.STRING,
            "number": types.Type.NUMBER,
            "integer": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "object": types.Type.OBJECT,
            "array": types.Type.ARRAY
        }
        return type_map.get(type_str, types.Type.STRING)

    def _default_question(self, question: str) -> str:
        return input(f"\n🤖 Agent asks: {question}\n> ")

    def _default_confirmation(self, action: str) -> bool:
        response = input(f"\n⚠️  Confirm: {action}\n  Type 'yes': ")
        return response.lower() in ['yes', 'y', 'да']

    async def _generate_with_retry(self, **kwargs):
        """Ручной механизм повторных попыток"""
        max_retries = 5  # Пытаемся 5 раз
        base_delay = 5   # Ждем 5 секунд между попытками
        
        for attempt in range(max_retries):
            try:
                return self.client.models.generate_content(**kwargs)
            except Exception as e:
                error_str = str(e).lower()
                print(f"\n⚠️ Network Error (attempt {attempt+1}/{max_retries}): {e}")
                
                # Если ошибка 400 (Invalid Argument), ретрай не поможет, пробрасываем
                if "400" in error_str or "invalid" in error_str or "deadline" in error_str:
                    # Но иногда deadline - это тоже сетевая проблема в gRPC
                    if "deadline" not in error_str:
                         raise e

                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                else:
                    raise e

    async def execute_task(self, task: str) -> dict:
        self.context.set_task(task)
        self.running = True

        chat_history = [
            types.Content(
                role="user",
                parts=[types.Part(text=f"Task: {task}\n\nStart by analyzing the current page using get_page_content.")]
            )
        ]
        
        iteration = 0
        max_iterations = 50

        while self.running and iteration < max_iterations:
            iteration += 1

            try:
                # Используем нашу функцию с ретраями
                response = await self._generate_with_retry(
                    model=MODEL,
                    contents=chat_history,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        tools=self.tools,
                        temperature=0.7,
                        max_output_tokens=2000
                    )
                )

                if not response.candidates:
                    print("\n❌ Empty response")
                    break

                model_content = response.candidates[0].content
                chat_history.append(model_content)

                has_text = False
                function_calls = []

                for part in model_content.parts:
                    if part.text:
                        print(f"\n💭 {part.text[:250]}...")
                        has_text = True
                    if part.function_call:
                        function_calls.append(part.function_call)

                if not function_calls:
                    if not has_text:
                        chat_history.append(types.Content(
                            role="user",
                            parts=[types.Part(text="Proceed.")]
                        ))
                    continue

                function_response_parts = []

                for func_call in function_calls:
                    func_name = func_call.name
                    try:
                        func_args = dict(func_call.args)
                    except:
                        func_args = {}

                    print(f"\n🔧 {func_name}: {str(func_args)[:100]}")

                    result = await self._execute_tool(func_name, func_args)
                    
                    # Статус в консоль
                    status = "✓" if result.get("success") else "✗"
                    print(f"   {status} {str(result)[:100]}...")

                    # Контекст
                    self.context.add_action(
                        thought="",
                        action_type=func_name,
                        params=func_args,
                        result=result,
                        url=await self.browser.get_current_url()
                    )

                    if func_name == "report_result":
                        self.running = False
                        success = result.get("success", True)
                        print(f"\n{'✅' if success else '❌'} {result.get('result', '')}")
                        return result

                    function_response_parts.append(types.Part(
                        function_response=types.FunctionResponse(
                            name=func_name,
                            response=result
                        )
                    ))

                if function_response_parts:
                    chat_history.append(types.Content(
                        role="user",
                        parts=function_response_parts
                    ))

            except Exception as e:
                print(f"\n❌ Critical Loop Error: {e}")
                import traceback
                traceback.print_exc()
                
                # Если произошла критическая ошибка, которая не поймалась ретраем
                # Мы не можем просто добавить сообщение об ошибке, так как это может сломать историю
                # Лучше остановить выполнение
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Max iterations reached"}

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        try:
            if not params: params = {}
            
            if tool_name == "navigate":
                return await self.browser.navigate(params.get("url", ""))
            
            elif tool_name == "click":
                return await self.browser.click(params.get("selector", ""))
            
            elif tool_name == "type_text":
                return await self.browser.type_text(params.get("selector", ""), params.get("text", ""))
            
            elif tool_name == "fill":
                return await self.browser.fill(params.get("selector", ""), params.get("text", ""))
            
            elif tool_name == "press_key":
                return await self.browser.press_key(params.get("key", "Enter"))
            
            elif tool_name == "scroll":
                return await self.browser.scroll(params.get("direction", "down"))
            
            elif tool_name == "get_page_content":
                if not self.browser.page: return {"success": False, "error": "No browser"}
                analyzer = PageAnalyzer(self.browser.page)
                content = await analyzer.get_compact_state()
                return {"success": True, "content": content}
            
            elif tool_name == "go_back":
                return await self.browser.go_back()
            
            elif tool_name == "wait":
                try: s = float(params.get("seconds", 1))
                except: s = 1
                return await self.browser.wait(min(s, 10))
            
            elif tool_name == "hover":
                return await self.browser.hover(params.get("selector", ""))
            
            elif tool_name == "ask_user":
                answer = self.on_user_question(params.get("question", "?"))
                return {"success": True, "user_response": answer}
            
            elif tool_name == "request_confirmation":
                approved = self.on_confirmation(params.get("action_description", "Action"))
                return {"success": True, "approved": approved}
            
            elif tool_name == "save_finding":
                self.context.add_finding(params.get("finding", ""))
                return {"success": True}
            
            elif tool_name == "report_result":
                success = params.get("success", True)
                if isinstance(success, str): success = success.lower() == 'true'
                return {"success": success, "result": params.get("result", "")}
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop(self):
        self.running = False