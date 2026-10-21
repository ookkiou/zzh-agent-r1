def ranges_overlap(a_start, a_end, b_start, b_end):
    return max(a_start, b_start) < min(a_end, b_end)
