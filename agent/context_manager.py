"""
Менеджер контекста - управление историей действий и памятью агента
"""
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Action:
    """Запись о действии агента"""
    timestamp: datetime
    thought: str
    action_type: str
    action_params: Dict[str, Any]
    result: Dict[str, Any]
    page_url: str


@dataclass
class ContextManager:
    """Управление контекстом и памятью агента"""
    task: str = ""
    actions: List[Action] = field(default_factory=list)
    max_history: int = 20
    important_findings: List[str] = field(default_factory=list)
    current_subtask: str = ""
    errors_count: int = 0

    def set_task(self, task: str):
        """Установить основную задачу"""
        self.task = task
        self.actions = []
        self.important_findings = []
        self.current_subtask = ""
        self.errors_count = 0

    def add_action(self, thought: str, action_type: str, params: dict, result: dict, url: str):
        """Добавить действие в историю"""
        action = Action(
            timestamp=datetime.now(),
            thought=thought,
            action_type=action_type,
            action_params=params,
            result=result,
            page_url=url
        )
        self.actions.append(action)

        if not result.get("success", True):
            self.errors_count += 1

        if len(self.actions) > self.max_history:
            self.actions = self.actions[-self.max_history:]

    def add_finding(self, finding: str):
        """Добавить важное наблюдение"""
        self.important_findings.append(finding)
        if len(self.important_findings) > 10:
            self.important_findings = self.important_findings[-10:]

    def set_subtask(self, subtask: str):
        """Установить текущую подзадачу"""
        self.current_subtask = subtask

    def get_context_summary(self) -> str:
        """Получить краткую сводку контекста"""
        lines = []
        lines.append(f"=== Task: {self.task} ===")

        if self.current_subtask:
            lines.append(f"Current subtask: {self.current_subtask}")

        if self.important_findings:
            lines.append("\n--- Important Findings ---")
            for finding in self.important_findings[-5:]:
                lines.append(f"  * {finding}")

        lines.append(f"\n--- Recent Actions ({len(self.actions)} total, {self.errors_count} errors) ---")
        for action in self.actions[-10:]:
            result_status = "OK" if action.result.get("success", False) else "FAIL"
            params_str = str(action.action_params)[:60]
            lines.append(f"  [{result_status}] {action.action_type}: {params_str}")
            if not action.result.get("success", True):
                error = action.result.get('error', 'Unknown')[:60]
                lines.append(f"      Error: {error}")

        return "\n".join(lines)

    def get_last_error(self) -> str:
        """Получить последнюю ошибку"""
        for action in reversed(self.actions):
            if not action.result.get("success", True):
                return action.result.get("error", "Unknown error")
        return ""