def screen_process(parameters, response, player, session_memory):
    if player: player.write_log("SYS: Vision module captured screen.")
    # Vision module operates silently in the background