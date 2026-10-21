def is_abundant(n):
    fctrsum = sum([fctr for fctr in range(0, n) if n % fctr == 0])
    return fctrsum > n
