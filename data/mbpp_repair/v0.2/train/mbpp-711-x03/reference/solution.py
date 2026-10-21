def product_Equal(n):
    if n < 10:
        return False
    prodOdd = 1
    prodEven = 1
    while n > 0:
        digit = n % 10
        prodOdd *= digit
        n = n // 10
        if n == 0:
            break
        digit = n % 10
        prodEven *= digit
        n = n // 10
    if prodOdd == prodEven:
        return True
    return False
