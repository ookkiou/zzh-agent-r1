def left_rotate(s, d):
    tmp = s[d:] + s[0:d]
    return tmp
