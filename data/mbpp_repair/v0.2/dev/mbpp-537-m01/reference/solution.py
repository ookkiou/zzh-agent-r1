def first_repeated_word(str1):
    temp = set()
    for word in str1.split():
        if word in temp:
            return word
        else:
            temp.add(word)
    return 'None'
