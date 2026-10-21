def parse_bool(text):
    value = text.strip().lower()
    if value in ("true", "yes", "1"):
        return True
    if value in ("false", "no", "0"):
        return False
    return None
