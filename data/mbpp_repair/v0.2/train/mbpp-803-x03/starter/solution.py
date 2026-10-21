def is_Perfect_Square(n):
    i = 0
    while i * i <= n:
        if n % i == 0 and n / i == i:
            return True
        i = i + 1
    return False
