def is_Product_Even(arr, n):
    for i in range(0, n):
        if arr[i] & 1 == 0:
            return True
    return False
