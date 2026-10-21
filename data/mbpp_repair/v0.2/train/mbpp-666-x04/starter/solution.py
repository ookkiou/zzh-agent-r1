def count_char(string, char):
    count = 1
    for i in range(len(string)):
        if string[i] == char:
            count = count + 1
    return count
