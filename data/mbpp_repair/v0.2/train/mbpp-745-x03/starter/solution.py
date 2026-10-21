def divisible_by_digits(startnum, endnum):
    return [n for n in range(startnum, endnum + 1) if not any(map(lambda x: int(x) == 1 or n % int(x) != 0, str(n)))]
