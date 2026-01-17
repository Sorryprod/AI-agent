"""
Контроллер браузера.
Загружает локальное расширение (extension/) в браузер.
"""
import asyncio
import os
from playwright.async_api import async_playwright, Page, BrowserContext

class BrowserController:
    def __init__(self, user_data_dir: str, headless: bool = False, viewport: dict = None):
        self.user_data_dir = user_data_dir
        self.headless = headless # Расширения работают ТОЛЬКО в headful режиме
        self.viewport = viewport
        self.playwright = None
        self.context = None
        self.page = None

    async def start(self):
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)

        # Путь к папке с расширением (абсолютный путь надежнее)
        extension_path = os.path.abspath("./extension")

        self.playwright = await async_playwright().start()

        # Аргументы для загрузки расширения
        args = [
            f"--disable-extensions-except={extension_path}",
            f"--load-extension={extension_path}",
            "--start-maximized",
            "--disable-blink-features=AutomationControlled"
        ]

        self.context = await self.playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=False, # Расширения не работают в headless=True
            args=args,
            viewport=None, # Отключаем viewport, чтобы работало --start-maximized
            locale='ru-RU',
            ignore_https_errors=True
        )

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        self.page.set_default_timeout(15000)
        return self

    # ... (Остальные методы: stop, navigate, click и т.д. остаются без изменений) ...
    # Скопируйте их из предыдущего рабочего варианта browser_controller.py
    async def stop(self):
        if self.context: await self.context.close()
        if self.playwright: await self.playwright.stop()
        
    async def navigate(self, url: str):
        if not url.startswith(('http', 'https')): url = 'https://' + url
        try:
            await self.page.goto(url, wait_until='domcontentloaded')
            return {"success": True, "url": self.page.url}
        except Exception as e: return {"success": False, "error": str(e)}

    async def click(self, selector: str):
        try:
            # Упрощенная логика для краткости
            try: await self.page.click(selector, timeout=2000)
            except: await self.page.click(f"text={selector}", timeout=2000)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}
    
    async def type_text(self, selector: str, text: str):
        try:
            await self.page.fill(selector, text)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def press_key(self, key: str):
        await self.page.keyboard.press(key)
        return {"success": True}
        
    async def scroll(self, direction="down"):
        if direction == "down": await self.page.mouse.wheel(0, 500)
        else: await self.page.mouse.wheel(0, -500)
        return {"success": True}
        
    async def wait(self, seconds=1):
        await asyncio.sleep(seconds)
        return {"success": True}
        
    async def go_back(self):
        await self.page.go_back()
        return {"success": True}
    
    async def get_current_url(self):
        return self.page.url
        
    async def hover(self, selector):
        await self.page.hover(selector)
        return {"success": True}
        
    async def fill(self, selector, text):
        await self.page.fill(selector, text)
        return {"success": True}