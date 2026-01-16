"""
Контроллер браузера с поддержкой persistent sessions
Оптимизирован для скорости: убраны долгие ожидания загрузки сети
"""
import asyncio
import os
import base64
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional


class BrowserController:
    def __init__(self, user_data_dir: str, headless: bool = False, viewport: dict = None):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.viewport = viewport or {"width": 1280, "height": 900}
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self):
        """Запуск браузера"""
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)

        self.playwright = await async_playwright().start()

        self.context = await self.playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=self.headless,
            args=[
                '--start-maximized', 
                '--disable-blink-features=AutomationControlled',
                '--disable-notifications' # Блокируем уведомления
            ],
            viewport=self.viewport,
            locale='ru-RU',
            # slow_mo убран для скорости
            ignore_https_errors=True
        )

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        self.page.set_default_timeout(15000) # Таймаут 15 сек достаточно
        return self

    async def stop(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str) -> dict:
        """Переход по URL (Быстрый)"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # wait_until='domcontentloaded' - не ждем картинки и скрипты аналитики
            response = await self.page.goto(url, wait_until='domcontentloaded')
            
            # Ждем всего 2 секунды для прогрузки основного JS
            await asyncio.sleep(2) 

            return {
                "success": True,
                "url": self.page.url,
                "title": await self.page.title(),
                "status": response.status if response else 200
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str) -> dict:
        try:
            # 1. Если селектор похож на текст (содержит пробелы или кириллицу)
            if " " in selector or any(ord(c) > 128 for c in selector):
                # Пробуем кликнуть по тексту
                try:
                    await self.page.click(f"text={selector}", timeout=2000)
                    await asyncio.sleep(1)
                    return {"success": True, "message": f"Clicked text '{selector}'"}
                except:
                    # Если точного совпадения нет, пробуем частичное
                    try:
                        # Используем :text-matches для нечеткого поиска (case-insensitive)
                        await self.page.click(f":text-matches('{selector}', 'i')", timeout=2000)
                        await asyncio.sleep(1)
                        return {"success": True, "message": f"Clicked text match '{selector}'"}
                    except:
                        pass # Идем дальше к CSS селектору

            # 2. Если это CSS селектор (id, class)
            try:
                await self.page.click(selector, timeout=2000)
                await asyncio.sleep(1)
                return {"success": True, "message": f"Clicked css '{selector}'"}
            except:
                pass
            
            # 3. JS клик как последнее средство (самый мощный)
            # Ищем элемент, который содержит этот текст
            found = await self.page.evaluate(f'''(text) => {{
                const elements = [...document.querySelectorAll('button, a, div, span')];
                const el = elements.find(e => e.innerText && e.innerText.includes(text) && e.offsetParent !== null);
                if (el) {{
                    el.click();
                    return true;
                }}
                return false;
            }}''', selector)
            
            if found:
                await asyncio.sleep(1)
                return {"success": True, "message": f"JS Clicked '{selector}'"}
            
            return {"success": False, "error": f"Element not found: {selector}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, selector: str, text: str, clear: bool = True) -> dict:
        try:
            # Фокус и ввод
            await self.page.focus(selector)
            if clear:
                await self.page.fill(selector, "")
            await self.page.type(selector, text, delay=10) # Быстрая печать
            return {"success": True, "message": f"Typed '{text}'"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def fill(self, selector: str, text: str) -> dict:
        """Мгновенное заполнение"""
        try:
            await self.page.fill(selector, text)
            return {"success": True, "message": f"Filled '{text}'"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def press_key(self, key: str) -> dict:
        try:
            await self.page.keyboard.press(key)
            await asyncio.sleep(0.5)
            return {"success": True, "message": f"Pressed {key}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 500) -> dict:
        try:
            if direction == "down":
                await self.page.mouse.wheel(0, amount)
            elif direction == "up":
                await self.page.mouse.wheel(0, -amount)
            await asyncio.sleep(0.5)
            return {"success": True, "message": f"Scrolled {direction}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait(self, seconds: float) -> dict:
        await asyncio.sleep(seconds)
        return {"success": True, "message": f"Waited {seconds}s"}

    async def go_back(self) -> dict:
        await self.page.go_back()
        return {"success": True, "url": self.page.url}

    async def get_current_url(self) -> str:
        return self.page.url if self.page else ""

    async def hover(self, selector: str) -> dict:
        try:
            await self.page.hover(selector)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}