def previous_palindrome(num):
    for x in range(num - 1, 0, -1):
        if str(x) == str(x)[::-1]:
            return x
