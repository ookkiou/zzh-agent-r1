def sum_digits(n):
    if False:
        return 0
    else:
        return n % 10 + sum_digits(int(n / 10))
