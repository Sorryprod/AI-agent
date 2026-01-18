"""
Анализатор страницы - FULL SEMANTIC VISION
Видит все тексты (цены, названия), а не только кнопки.
Строит полное дерево для понимания контекста.
"""
import os
from playwright.async_api import Page
from config import DEBUG_MODE

class PageAnalyzer:
    def __init__(self, page: Page):
        self.page = page

    async def get_compact_state(self) -> str:
        tree = await self.page.evaluate('''() => {
            // КОНФИГУРАЦИЯ
            const MAX_TEXT_LEN = 100;
            const MAX_DEPTH = 20; // Глубокая вложенность для сложных сайтов
            let robotId = 0;
            
            // Чистим старые ID
            document.querySelectorAll('[data-r-id]').forEach(el => el.removeAttribute('data-r-id'));

            // Проверка видимости
            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 1 || rect.height < 1) return false;
                // Чуть шире экрана (на 1000px), чтобы видеть предзагруженный контент
                if (rect.bottom < -200 || rect.top > window.innerHeight + 800) return false;
                
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
            }

            function cleanText(text) {
                return (text || '').replace(/\\s+/g, ' ').trim().substring(0, MAX_TEXT_LEN);
            }

            // Главная функция обхода
            function traverse(element, depth) {
                if (depth > MAX_DEPTH) return '';
                if (!isVisible(element)) return '';

                let output = '';
                const tagName = element.tagName.toLowerCase();
                const style = window.getComputedStyle(element);
                
                // 1. ОПРЕДЕЛЕНИЕ ТИПА (Интерактивный?)
                const isClickable = (
                    tagName === 'a' || tagName === 'button' || tagName === 'input' || 
                    tagName === 'select' || tagName === 'textarea' ||
                    element.getAttribute('role') === 'button' ||
                    style.cursor === 'pointer' ||
                    element.onclick != null
                );

                // 2. ПОЛУЧЕНИЕ СОБСТВЕННОГО ТЕКСТА
                // (Текст, который лежит прямо в этом элементе, а не в детях)
                let directText = '';
                if (element.childNodes) {
                    Array.from(element.childNodes).forEach(node => {
                        if (node.nodeType === Node.TEXT_NODE) {
                            directText += node.textContent;
                        }
                    });
                }
                directText = cleanText(directText);
                
                // Атрибуты (для контекста)
                const label = cleanText(element.getAttribute('aria-label') || element.getAttribute('title') || element.getAttribute('placeholder'));
                const role = element.getAttribute('role');

                // 3. РЕШЕНИЕ: ДОБАВЛЯТЬ ЛИ В ДЕРЕВО?
                // Добавляем, если:
                // - Это кнопка/ссылка (даже пустая)
                // - Это контейнер с текстом (цена, название)
                // - Это картинка (важно для еды)
                
                let shouldShow = isClickable || (directText.length > 1) || (label.length > 1) || tagName === 'img';

                if (shouldShow) {
                    const indent = '  '.repeat(depth);
                    let line = `${indent}`;
                    
                    // Если можно кликнуть - даем ID
                    if (isClickable) {
                        robotId++;
                        element.setAttribute('data-r-id', robotId);
                        line += `[${robotId}] <${tagName}>`;
                    } else {
                        // Просто тег (для структуры)
                        line += `<${tagName}>`;
                    }

                    // Добавляем контент
                    if (directText) line += ` "${directText}"`;
                    if (label) line += ` [Label: ${label}]`;
                    if (tagName === 'img' && element.alt) line += ` [Img: ${cleanText(element.alt)}]`;
                    
                    output += line + '\\n';
                }

                // 4. РЕКУРСИЯ
                // Если элемент - это просто контейнер без текста, мы не выводим его строку,
                // но ОБЯЗАТЕЛЬНО идем внутрь искать детей.
                // Но если мы уже вывели строку (shouldShow=true), то дети будут с отступом.
                // Если нет (shouldShow=false), то дети будут на том же уровне (flattening),
                // чтобы не плодить пустые <div>.
                
                const childDepth = shouldShow ? depth + 1 : depth;
                
                for (const child of element.children) {
                    output += traverse(child, childDepth);
                }

                return output;
            }

            const structure = traverse(document.body, 0);
            
            if (!structure.trim()) return "Page seems empty (Scripts loading?). Wait...";
            
            return `URL: ${window.location.href}\\nSCROLL: ${window.scrollY}\\n\\n${structure}`;
        }''')

        # Сохраняем дамп, чтобы ты мог проверить
        if DEBUG_MODE:
            try:
                with open("debug_tree.txt", "w", encoding="utf-8") as f:
                    f.write(tree)
                print(f"👀 [DEBUG] Snapshot saved ({len(tree)} chars)")
            except: pass

        return tree