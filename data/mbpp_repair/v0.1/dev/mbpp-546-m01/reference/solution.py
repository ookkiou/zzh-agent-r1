def last_occurence_char(string, char):
    flag = -1
    for i in range(len(string)):
        if string[i] == char:
            flag = i
    if flag == -1:
        return None
    else:
        return flag + 1
