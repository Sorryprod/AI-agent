"""
Анализатор страницы - SUPER LITE
Минимальный вес данных для устранения ошибок 'Server disconnected'
"""
from typing import List, Dict, Any
from playwright.async_api import Page


class PageAnalyzer:
    def __init__(self, page: Page):
        self.page = page

    async def get_compact_state(self) -> str:
        """Сжатое представление для LLM (Только интерактивные элементы)"""
        # Запускаем скрипт, который вернет уже отформатированную строку
        # Это быстрее, чем передавать JSON и форматировать в Python
        report = await self.page.evaluate('''() => {
            const selectors = [
                'button', 'a[href]', 'input', '[role="button"]', 
                'textarea', '[contenteditable]'
            ];
            
            let lines = [];
            lines.push(`URL: ${window.location.href}`);
            lines.push("--- INTERACTIVE ---");
            
            const seen = new Set();
            let count = 0;
            
            document.querySelectorAll(selectors.join(',')).forEach(el => {
                if (count >= 25) return; // ЖЕСТКИЙ ЛИМИТ: 25 элементов

                const rect = el.getBoundingClientRect();
                // Только видимые элементы в верхнем экране
                if (rect.height < 5 || rect.width < 5) return;
                if (rect.top < 0 || rect.top > 1200) return; // Только первый экран
                
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return;

                // Получаем текст
                let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
                if (text.length > 30) text = text.substring(0, 30) + '...';
                
                // Если нет текста и нет ID - элемент бесполезен для LLM
                if (!text && !el.id) return;

                // Генерируем селектор
                let selector = el.tagName.toLowerCase();
                if (el.id) {
                    selector = '#' + el.id;
                } else if (text) {
                     // Если есть уникальный текст, предлагаем использовать его
                     // Это подсказка для LLM
                     selector = `text="${text}"`; 
                } else if (el.className && typeof el.className === 'string') {
                     const cls = el.className.split(' ')[0];
                     if (cls) selector += '.' + cls;
                }
                
                const key = selector + text;
                if (seen.has(key)) return;
                seen.add(key);
                
                // Формируем строку для отчета
                lines.push(`<${el.tagName.toLowerCase()}> "${text}" -> ${selector}`);
                count++;
            });
            
            // Добавляем немного контекста, если элементов мало
            if (count < 5) {
                const bodyText = document.body.innerText.replace(/\\s+/g, ' ').substring(0, 300);
                lines.push("--- TEXT ---");
                lines.push(bodyText);
            }
            
            return lines.join('\\n');
        }''')

        return report