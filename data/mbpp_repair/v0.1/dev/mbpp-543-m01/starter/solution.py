def count_digits(num1, num2):
    number = num1 + num2
    count = 1
    while number > 0:
        number = number // 10
        count = count + 1
    return count
