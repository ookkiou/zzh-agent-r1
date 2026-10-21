def rotate_left(items, k):
    if not items:
        return []
    offset = k % len(items)
    return items[offset:] + items[:offset]
