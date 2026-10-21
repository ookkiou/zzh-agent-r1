def check_greater(arr, number):
    arr.sort()
    if number > arr[-1]:
        return 'Yes, the entered number is greater than those in the array'
    else:
        return 'No, entered number is less than those in the array'
