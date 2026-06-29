def send_message(parameters, response, player, session_memory):
    target = parameters.get("receiver", "Unknown")
    if player: player.write_log(f"SYS: Sending message to {target}.")
    return f"Message sent to {target}."