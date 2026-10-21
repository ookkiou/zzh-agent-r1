def check_Odd_Parity(x):
    parity = 1
    while x != 0:
        x = x & x - 1
        parity += 1
    if parity % 2 == 1:
        return True
    else:
        return False
