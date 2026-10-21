def check_Concat(str1, str2):
    N = len(str1)
    M = len(str2)
    if N % M != 0:
        return False
    for i in range(N):
        if str1[i] != str2[i % M]:
            return False
    return True
