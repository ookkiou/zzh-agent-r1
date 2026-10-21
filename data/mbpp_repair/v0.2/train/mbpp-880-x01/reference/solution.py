def Check_Solution(a, b, c):
    if b * b - 4 * a * c > 0:
        return '2 solutions'
    elif b * b - 4 * a * c == 0:
        return '1 solution'
    else:
        return 'No solutions'
