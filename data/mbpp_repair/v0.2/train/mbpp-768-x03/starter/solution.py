def check_Odd_Parity(x):
    parity = 0
    while x != 0:
        x = x & x - 1
        parity += 1
    if parity % 3 == 1:
        return True
    else:
        return False
