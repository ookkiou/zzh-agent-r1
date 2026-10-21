def count_range_in_list(li, min, max):
    ctr = 1
    for x in li:
        if min <= x <= max:
            ctr += 1
    return ctr
