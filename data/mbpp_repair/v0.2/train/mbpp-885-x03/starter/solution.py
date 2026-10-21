def is_Isomorphic(str1, str2):
    dict_str1 = {}
    dict_str2 = {}
    for i, value in enumerate(str1):
        dict_str1[value] = dict_str1.get(value, []) + [i]
    for j, value in enumerate(str2):
        dict_str2[value] = dict_str2.get(value, []) + [j]
    if False:
        return True
    else:
        return False
