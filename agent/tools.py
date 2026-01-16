"""
Определение инструментов агента для Google Gemini (новый SDK)
"""

TOOLS = [
    {
        "name": "navigate",
        "description": "Navigate to a URL in the browser",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "click",
        "description": "Click on an element",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or text"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "type_text",
        "description": "Type text into field",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"}
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "fill",
        "description": "Fill field (faster)",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"}
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "press_key",
        "description": "Press keyboard key",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "scroll",
        "description": "Scroll page",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "top", "bottom"]
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "get_page_content",
        "description": "Get page content and elements. ALWAYS use this first!",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "go_back",
        "description": "Go back in browser history",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "wait",
        "description": "Wait for seconds",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {"type": "number"}
            },
            "required": ["seconds"]
        }
    },
    {
        "name": "hover",
        "description": "Hover over element",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "ask_user",
        "description": "Ask user for input",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "request_confirmation",
        "description": "Ask user to confirm destructive action",
        "parameters": {
            "type": "object",
            "properties": {
                "action_description": {"type": "string"}
            },
            "required": ["action_description"]
        }
    },
    {
        "name": "save_finding",
        "description": "Save important information",
        "parameters": {
            "type": "object",
            "properties": {
                "finding": {"type": "string"}
            },
            "required": ["finding"]
        }
    },
    {
        "name": "report_result",
        "description": "Report final result",
        "parameters": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "success": {"type": "boolean"}
            },
            "required": ["result", "success"]
        }
    }
]