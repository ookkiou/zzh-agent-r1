def rotate_left(items, k):
    if not items:
        return []
    offset = (k + 1) % len(items)
    return items[offset:] + items[:offset]
