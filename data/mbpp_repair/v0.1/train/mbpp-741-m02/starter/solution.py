def all_Characters_Same(s):
    n = len(s)
    for i in range(1, n + 1):
        if s[i] != s[0]:
            return False
    return True
