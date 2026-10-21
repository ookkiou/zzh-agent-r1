def count_words(text):
    count = 0
    for word in text.split():
        count += 1
    return count
