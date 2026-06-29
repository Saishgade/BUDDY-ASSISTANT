import json
import os

MEMORY_FILE = "memory.json"

def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def update_memory(new_data: dict):
    data = load_memory()
    data.update(new_data)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def format_memory_for_prompt(memory: dict) -> str:
    if not memory:
        return ""
    return f"[USER MEMORY]\n{json.dumps(memory, indent=2)}\n\n"

def should_extract_memory(user_text: str, buddy_text: str, api_key: str) -> bool:
    return False

def extract_memory(user_text: str, buddy_text: str, api_key: str) -> dict:
    return {}