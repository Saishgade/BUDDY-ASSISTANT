def web_search(parameters, player):
    query = parameters.get("query", "")
    if player: player.write_log(f"SYS: Searching web for -> {query}")
    return f"Web search results for '{query}' retrieved."