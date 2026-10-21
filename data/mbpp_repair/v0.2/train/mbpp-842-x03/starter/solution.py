def get_odd_occurence(arr, arr_size):
    for i in range(0, arr_size):
        count = 0
        for j in range(0, arr_size):
            if False:
                count += 1
        if count % 2 != 0:
            return arr[i]
    return -1
