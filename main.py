"""
Главная точка входа - запуск AI Browser Agent
"""
import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from agent.browser_controller import BrowserController
from agent.ai_agent import AIAgent
from config import HEADLESS, VIEWPORT, USER_DATA_DIR


console = Console()


def handle_user_question(question: str) -> str:
    """Обработчик вопросов от агента"""
    console.print(f"\n[bold cyan]🤖 Agent needs your input:[/bold cyan]")
    return Prompt.ask(f"   {question}")


def handle_confirmation(action_description: str) -> bool:
    """Обработчик запросов подтверждения (Security Layer)"""
    console.print(f"\n[bold yellow]Action:[/bold yellow] {action_description}")
    return Confirm.ask("[bold red]Do you approve this action?[/bold red]")


async def main():
    console.print(Panel.fit(
        "[bold blue]🌐 AI Browser Agent[/bold blue]\n\n"
        "Autonomous browser automation powered by Google Gemini (Free).\n"
        "• Persistent sessions - log in once, stay logged in\n"
        "• Security layer - confirms before destructive actions\n"
        "• Adaptive - handles errors and retries intelligently",
        title="Welcome",
        border_style="blue"
    ))

    console.print(f"\n[dim]Session data stored in: {USER_DATA_DIR}[/dim]")
    console.print("[dim]Tip: Log into your accounts once, and the agent will remember[/dim]\n")

    # Запуск браузера
    console.print("[yellow]Starting browser...[/yellow]")
    browser = BrowserController(
        user_data_dir=USER_DATA_DIR,
        headless=HEADLESS,
        viewport=VIEWPORT
    )
    await browser.start()
    console.print("[green]✓ Browser ready![/green]\n")

    # Создаём агента
    agent = AIAgent(
        browser,
        on_user_question=handle_user_question,
        on_confirmation=handle_confirmation
    )

    try:
        while True:
            console.print("[bold]" + "─" * 60 + "[/bold]")
            task = Prompt.ask(
                "\n[bold green]Enter your task[/bold green]\n"
                "[dim](or 'quit' to exit, 'help' for examples)[/dim]"
            )

            if task.lower() in ['quit', 'exit', 'q']:
                break

            if task.lower() == 'help':
                console.print(Panel(
                    "[cyan]Example tasks:[/cyan]\n\n"
                    "📧 Email: 'Прочитай последние 10 писем в яндекс почте и удали спам'\n\n"
                    "🍔 Food: 'Закажи бургер и картошку на Яндекс.Еде'\n\n"
                    "💼 Jobs: 'Найди 3 вакансии AI-инженера на hh.ru и откликнись'\n\n"
                    "🔍 Search: 'Найди на Google информацию о погоде в Москве'\n\n"
                    "🛒 Shopping: 'Найди iPhone 15 на Wildberries дешевле 80000'",
                    title="Examples"
                ))
                continue

            if not task.strip():
                continue

            console.print(f"\n[bold]📋 Task:[/bold] {task}")
            console.print("[dim]Watch the browser window...[/dim]\n")

            try:
                result = await agent.execute_task(task)

                if result.get("success"):
                    console.print(Panel(
                        f"[green]{result.get('result', 'Done')}[/green]",
                        title="✅ Task Completed",
                        border_style="green"
                    ))
                else:
                    console.print(Panel(
                        f"[red]{result.get('error', result.get('result', 'Failed'))}[/red]",
                        title="❌ Task Failed",
                        border_style="red"
                    ))

            except KeyboardInterrupt:
                console.print("\n[yellow]Task interrupted[/yellow]")
                agent.stop()
            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]")

    finally:
        console.print("\n[yellow]Closing browser...[/yellow]")
        await browser.stop()
        console.print("[green]Goodbye! 👋[/green]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)