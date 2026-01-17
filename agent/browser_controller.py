"""
Контроллер браузера - SMART INTERACTIONS
Умеет кликать по временным ID, делает Hover перед кликом, пробивает оверлеи.
"""
import asyncio
import os
from playwright.async_api import async_playwright, Page, BrowserContext

class BrowserController:
    def __init__(self, user_data_dir: str, headless: bool = False, viewport: dict = None):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.viewport = viewport
        self.playwright = None
        self.context = None
        self.page = None

    async def start(self):
        # ... (код инициализации без изменений, скопируйте из прошлых версий) ...
        # Убедитесь, что загружаете расширение, если используете локальную версию
        if not os.path.exists(self.user_data_dir): os.makedirs(self.user_data_dir)
        extension_path = os.path.abspath("./extension")
        self.playwright = await async_playwright().start()
        args = [f"--disable-extensions-except={extension_path}", f"--load-extension={extension_path}", "--start-maximized", "--disable-blink-features=AutomationControlled"]
        self.context = await self.playwright.chromium.launch_persistent_context(
            self.user_data_dir, headless=False, args=args, viewport=None, locale='ru-RU', ignore_https_errors=True
        )
        if self.context.pages: self.page = self.context.pages[0]
        else: self.page = await self.context.new_page()
        self.page.set_default_timeout(15000)
        return self

    async def stop(self):
        if self.context: await self.context.close()
        if self.playwright: await self.playwright.stop()

    async def navigate(self, url: str):
        if not url.startswith(('http', 'https')): url = 'https://' + url
        try:
            await self.page.goto(url, wait_until='domcontentloaded')
            await asyncio.sleep(2) # Даем JS прогрузиться
            return {"success": True, "url": self.page.url}
        except Exception as e: return {"success": False, "error": str(e)}

    # --- ГЛАВНОЕ УЛУЧШЕНИЕ: УМНЫЙ КЛИК ---
    async def click(self, selector: str):
        try:
            target = None
            
            # 1. Поиск по ID от анализатора (самый надежный)
            # Если LLM присылает "[12]", мы ищем data-ai-id="12"
            if selector.startswith('[') and selector.endswith(']'):
                ai_id = selector.strip('[]')
                target = await self.page.query_selector(f'[data-ai-id="{ai_id}"]')
            
            # 2. Поиск по тексту (text="...")
            if not target and 'text=' in selector:
                # Используем движок Playwright
                try: target = await self.page.wait_for_selector(selector, timeout=2000)
                except: pass

            # 3. Стандартный CSS селектор
            if not target:
                try: target = await self.page.query_selector(selector)
                except: pass

            if target:
                # Эмуляция поведения человека
                await target.scroll_into_view_if_needed()
                
                # Hover часто нужен для меню и кнопок в E-commerce
                try: await target.hover(timeout=1000)
                except: pass 
                
                await asyncio.sleep(0.3)
                
                # Клик с force=True (пробивает прозрачные оверлеи)
                await target.click(force=True)
                
                await asyncio.sleep(1) # Ждем реакции сайта
                return {"success": True, "message": f"Clicked {selector}"}
            else:
                return {"success": False, "error": f"Element not found: {selector}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ... (Остальные методы type_text, fill, press_key, scroll и т.д. без изменений) ...
    async def type_text(self, selector: str, text: str):
        try: await self.page.fill(selector, text); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}
    
    async def fill(self, selector: str, text: str):
        return await self.type_text(selector, text)

    async def press_key(self, key: str):
        try: await self.page.keyboard.press(key); await asyncio.sleep(0.5); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}
        
    async def scroll(self, direction="down"):
        try:
            if direction == "down": await self.page.mouse.wheel(0, 600)
            else: await self.page.mouse.wheel(0, -600)
            await asyncio.sleep(0.5)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}
        
    async def wait(self, seconds=1):
        await asyncio.sleep(seconds)
        return {"success": True}
        
    async def go_back(self):
        await self.page.go_back()
        return {"success": True}
    
    async def hover(self, selector):
        try: await self.page.hover(selector); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}