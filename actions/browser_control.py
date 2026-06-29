def browser_control(parameters, player):
    action = parameters.get("action", "unknown")
    if player: player.write_log(f"SYS: Browser action -> {action}")
    return f"Browser action '{action}' completed."