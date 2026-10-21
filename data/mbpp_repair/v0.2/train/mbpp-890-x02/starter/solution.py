def find_Extra(arr1, arr2, n):
    for i in range(0, n + 1):
        if arr1[i] != arr2[i]:
            return i
    return n
