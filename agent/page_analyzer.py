"""
Анализатор страницы - SEMANTIC TREE (Global Fix)
Строит иерархическую структуру страницы, чтобы агент понимал контекст
любой кнопки на любом сайте без хардкода.
"""
from playwright.async_api import Page

class PageAnalyzer:
    def __init__(self, page: Page):
        self.page = page

    async def get_compact_state(self) -> str:
        return await self.page.evaluate('''() => {
            // Конфигурация
            const CONFIG = {
                maxItems: 80, // Больше элементов для контекста
                minTextLength: 2,
                maxTextLength: 100
            };

            function cleanText(text) {
                return (text || '').replace(/\\s+/g, ' ').trim().substring(0, CONFIG.maxTextLength);
            }

            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 5 || rect.height < 5) return false;
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
            }

            // Оценка интерактивности элемента
            function getElementType(el) {
                const tag = el.tagName.toLowerCase();
                const style = window.getComputedStyle(el);
                const role = el.getAttribute('role');
                
                if (tag === 'button' || role === 'button' || style.cursor === 'pointer') return 'button';
                if (tag === 'a') return 'link';
                if (tag === 'input') {
                    const type = el.type;
                    if (['submit', 'button', 'reset'].includes(type)) return 'button';
                    if (['checkbox', 'radio'].includes(type)) return 'option';
                    return 'input';
                }
                if (tag === 'textarea' || el.isContentEditable) return 'input';
                if (tag === 'select') return 'select';
                return null;
            }

            // Генератор уникального селектора
            function getSelector(el) {
                if (el.id) return `#${CSS.escape(el.id)}`;
                
                // Пробуем уникальные атрибуты данных
                const dataAttrs = ['data-testid', 'data-test-id', 'data-qa', 'aria-label', 'name'];
                for (let attr of dataAttrs) {
                    if (el.hasAttribute(attr)) return `[${attr}="${el.getAttribute(attr)}"]`;
                }

                // Пробуем классы (только специфичные)
                if (el.className && typeof el.className === 'string') {
                    const classes = el.className.split(/\s+/).filter(c => c.length > 3 && !c.includes(':'));
                    if (classes.length > 0) return `.${classes.join('.')}`;
                }

                return el.tagName.toLowerCase();
            }

            let items = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
            let idCounter = 1;

            while (walker.nextNode()) {
                const el = walker.currentNode;
                if (!isVisible(el)) continue;

                const type = getElementType(el);
                const text = cleanText(el.innerText || el.value || el.placeholder || el.getAttribute('aria-label'));
                
                // Логика группировки:
                // Если элемент контейнер (div, li, article) и содержит текст, но не интерактивный -> это Контекст
                // Если элемент интерактивный -> это Действие
                
                // 1. Это интерактивный элемент?
                if (type) {
                    let label = text;
                    // Если текста нет, ищем внутри картинки или svg title
                    if (!label) {
                        const img = el.querySelector('img');
                        if (img && img.alt) label = `[Img: ${img.alt}]`;
                        else if (el.querySelector('svg')) label = '[Icon]';
                        else label = '[Action]';
                    }

                    // Ищем ближайший контекст (родителя с текстом), если кнопка "пустая" (типа "+")
                    let context = "";
                    if (label.length < 5 || label === '[Icon]') {
                        let parent = el.parentElement;
                        for(let i=0; i<3; i++) { // Идем вверх на 3 уровня
                            if (!parent) break;
                            const pText = cleanText(parent.innerText);
                            // Если в родителе текста больше, чем в кнопке
                            if (pText && pText.length > label.length && pText.length < 150) {
                                // Убираем текст самой кнопки из родителя
                                context = ` {Context: ${pText.replace(label, '').trim()}}`;
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }

                    const selector = getSelector(el);
                    
                    // Формат: [ID] <TYPE> "Label" {Context} -> Selector
                    // Если селектор слабый, добавляем text= для надежности
                    let robustSelector = selector;
                    if (!selector.includes('#') && !selector.includes('[') && label && label !== '[Icon]') {
                        robustSelector = `text="${label}"`;
                    }

                    items.push({
                        str: `[${idCounter}] <${type}> "${label}"${context} -> ${selector}`,
                        score: 10
                    });
                    el.setAttribute('data-ai-id', idCounter); // Метим элемент для точного клика по ID
                    idCounter++;
                }
                
                // 2. Это важный текст (заголовок, цена)?
                else if ((el.tagName.match(/^H[1-6]$/) || el.className.includes('price') || el.className.includes('title')) && text) {
                    items.push({
                        str: `   --- ${text} ---`,
                        score: 5
                    });
                }
            }

            // Сортировка и фильтрация (простая версия)
            // Возвращаем первые N элементов
            return [`URL: ${window.location.href}`, ...items.slice(0, CONFIG.maxItems).map(i => i.str)].join('\\n');
        }''')