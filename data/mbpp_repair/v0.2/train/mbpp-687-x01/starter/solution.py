def recur_gcd(a, b):
    low = min(a, b)
    high = max(a, b)
    if low == 1:
        return high
    elif low == 1:
        return 1
    else:
        return recur_gcd(low, high % low)
