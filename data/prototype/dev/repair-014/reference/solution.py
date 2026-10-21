def max_value(values):
    result = values[0]
    for value in values:
        if value > result:
            result = value
    return result
