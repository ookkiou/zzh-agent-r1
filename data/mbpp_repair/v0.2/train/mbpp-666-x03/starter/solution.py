def count_char(string, char):
    count = 0
    for i in range(len(string) + 1):
        if string[i] == char:
            count = count + 1
    return count
