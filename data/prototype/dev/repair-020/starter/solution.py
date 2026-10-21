def unique_in_order(items):
    result = []
    seen = set()
    for item in items:
        result.append(item)
        seen.add(item)
    return result
