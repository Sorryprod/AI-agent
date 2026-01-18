"""
Контроллер браузера - TRUE HUMAN INPUT
Имитирует физические нажатия клавиш для обхода защиты React/Vue.
"""
import asyncio
import os
from playwright.async_api import async_playwright, Page, BrowserContext

class BrowserController:
    # ... (init, start, stop, navigate без изменений) ...
    def __init__(self, user_data_dir: str, headless: bool = False, viewport: dict = None):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.viewport = viewport
        self.playwright = None
        self.context = None
        self.page = None

    async def start(self):
        if not os.path.exists(self.user_data_dir): os.makedirs(self.user_data_dir)
        extension_path = os.path.abspath("./extension")
        self.playwright = await async_playwright().start()
        args = [f"--disable-extensions-except={extension_path}", f"--load-extension={extension_path}", "--start-maximized", "--disable-blink-features=AutomationControlled"]
        self.context = await self.playwright.chromium.launch_persistent_context(self.user_data_dir, headless=False, args=args, viewport=None, locale='ru-RU', ignore_https_errors=True)
        if self.context.pages: self.page = self.context.pages[0]
        else: self.page = await self.context.new_page()
        self.page.set_default_timeout(10000)
        return self

    async def stop(self):
        if self.context: await self.context.close()
        if self.playwright: await self.playwright.stop()

    async def navigate(self, url: str):
        if not url.startswith(('http', 'https')): url = 'https://' + url
        try:
            await self.page.goto(url, wait_until='domcontentloaded')
            await asyncio.sleep(2)
            return {"success": True, "url": self.page.url}
        except Exception as e: return {"success": False, "error": str(e)}

    # --- CLICK (Stable) ---
    async def click(self, selector: str):
        try:
            target = None
            if selector.startswith('[') and selector.endswith(']'):
                ai_id = selector.strip('[]')
                target = await self.page.query_selector(f'[data-r-id="{ai_id}"]')
            
            if not target:
                try: target = await self.page.query_selector(selector)
                except: pass

            if target:
                await target.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                try: await target.evaluate("el => { el.style.outline = '3px solid red'; }")
                except: pass
                
                try: await target.click(timeout=2000)
                except: await target.evaluate("el => el.click()")
                
                try: await target.evaluate("el => { el.style.outline = ''; }")
                except: pass
                
                await asyncio.sleep(2)
                return {"success": True, "message": f"Clicked {selector}"}
            
            return {"success": False, "error": f"Not found: {selector}"}
        except Exception as e: return {"success": False, "error": str(e)}

    # --- TRUE HUMAN TYPING ---
    async def type_text(self, selector: str, text: str):
        try:
            target = None
            if selector.startswith('['):
                ai_id = selector.strip('[]')
                target = await self.page.query_selector(f'[data-r-id="{ai_id}"]')
            else:
                target = await self.page.query_selector(selector)

            if target:
                await target.scroll_into_view_if_needed()
                
                # 1. Фокус кликом (важно!)
                try: await target.click()
                except: pass
                
                # 2. Очистка через Ctrl+A -> Backspace (эмуляция, не JS)
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(0.2)

                # 3. Ввод посимвольно
                # Это вызывает все события keydown/keypress/input/keyup
                await self.page.keyboard.type(text, delay=100)
                
                await asyncio.sleep(0.5)
                return {"success": True}
            
            return {"success": False, "error": "Input not found"}
        except Exception as e: return {"success": False, "error": str(e)}

    async def press_key(self, key: str):
        try: 
            await self.page.keyboard.press(key)
            await asyncio.sleep(2)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}
        
    async def scroll(self, direction="down"):
        try:
            if direction == "down": await self.page.mouse.wheel(0, 600)
            else: await self.page.mouse.wheel(0, -600)
            await asyncio.sleep(1)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}
        
    async def wait(self, seconds=1):
        await asyncio.sleep(min(float(seconds), 10))
        return {"success": True}
        
    async def go_back(self):
        await self.page.go_back()
        return {"success": True}
    
    async def hover(self, selector): return {"success": True} 
    async def fill(self, selector, text): return await self.type_text(selector, text)