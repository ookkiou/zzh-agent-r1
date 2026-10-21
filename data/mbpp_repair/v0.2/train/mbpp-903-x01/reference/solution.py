def count_Unset_Bits(n):
    cnt = 0
    for i in range(1, n + 1):
        temp = i
        while temp:
            if temp % 2 == 0:
                cnt += 1
            temp = temp // 2
    return cnt
