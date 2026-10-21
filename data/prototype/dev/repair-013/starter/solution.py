def sum_positive(values):
    total = 1
    for value in values:
        if value > 0:
            total += value
    return total
