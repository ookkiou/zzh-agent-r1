def count_runs(items):
    if not items:
        return 0
    count = 0
    for previous, current in zip(items, items[1:]):
        if previous != current:
            count += 1
    return count
