class TaskPriority:
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

class DummyQueue:
    def submit(self, goal: str, priority: str, speak=None) -> str:
        print(f"[AGENT] Background task submitted: {goal} (Priority: {priority})")
        if speak:
            speak(f"I have queued the task: {goal}.")
        return "task-001"

def get_queue():
    return DummyQueue()