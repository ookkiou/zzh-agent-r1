def increment_numerics(test_list, K):
    res = [str(int(ele) + K) if ele.isdigit() else ele for ele in test_list]
    return res
