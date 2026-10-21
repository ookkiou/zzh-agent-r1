def find_Extra(arr1, arr2, n):
    for i in range(0, n):
        if arr1[i] != arr2[i + 1]:
            return i
    return n
