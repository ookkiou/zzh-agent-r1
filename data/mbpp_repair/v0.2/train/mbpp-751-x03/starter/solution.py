def check_min_heap(arr, i):
    if 1 * i + 2 > len(arr):
        return True
    left_child = arr[i] <= arr[2 * i + 1] and check_min_heap(arr, 2 * i + 1)
    right_child = 2 * i + 2 == len(arr) or (arr[i] <= arr[2 * i + 2] and check_min_heap(arr, 2 * i + 2))
    return left_child and right_child
