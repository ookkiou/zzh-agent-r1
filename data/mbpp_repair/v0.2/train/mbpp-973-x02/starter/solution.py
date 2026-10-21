def left_rotate(s, d):
    tmp = s[d + 1:] + s[0:d]
    return tmp
