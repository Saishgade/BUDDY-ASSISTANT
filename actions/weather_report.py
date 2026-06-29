def weather_action(parameters, player):
    city = parameters.get("city", "Unknown City")
    if player: player.write_log(f"SYS: Checking weather for {city}.")
    return f"Weather for {city} looks good."