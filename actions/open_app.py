def open_app(parameters, response, player):
    app = parameters.get("app_name", "Unknown App")
    if player: player.write_log(f"SYS: Opening application -> {app}")
    return f"Opened {app}."