"""Additional reviewed TRAIN domains and independently authored regression expectations.

Keep v0.1 specs and data immutable. Expectations below come from the stated
requirements and small hand calculations, never by executing a reference oracle.
"""

SPECS = {}


def spec(task_id, domain, pairs, note='Requirement, source, upstream assertions and expected values reviewed by coding assistant; not human signed off.'):
    if not 601 <= task_id <= 974 or task_id in SPECS or len(pairs) < 6:
        raise ValueError('Six independent train regression cases required')
    SPECS[task_id] = {'domain': domain, 'review_note': note,
        'cases': [{'id': f'regression_{i:02d}', 'args': args, 'expected': expected}
                  for i, (args, expected) in enumerate(pairs, 1)]}


spec(627, '严格递增的非负整数数组，长度<=30；start=0、end=len(array)-1；返回最小缺失非负整数，允许空数组。', [
    ([[],0,-1],0), ([[0],0,0],1), ([[1],0,0],0), ([[0,2],0,1],1),
    ([[0,1,3],0,2],2), ([[0,1,2,3,4],0,4],5)])
spec(666, 'ASCII 字符串与单个 ASCII 字符，区分大小写；返回字符出现次数，允许空串。', [
    (['','a'],0), (['aaa','a'],3), (['AaA','a'],1), (['hello','z'],0),
    (['  x ',' '],3), (['01010','0'],3)])
spec(672, '三个绝对值<=10**6 的整数；返回最大值，允许相等与负数。', [
    ([0,0,0],0), ([-3,-2,-1],-1), ([7,7,2],7), ([2,7,7],7),
    ([9,1,9],9), ([-10,0,-2],0)])
spec(675, '整数 x,y,m,n，m<=n；若 x+y 位于左闭右开区间 [m,n) 则返回20，否则返回原和。', [
    ([1,2,3,5],20), ([2,3,3,5],5), ([0,0,0,0],0), ([-2,1,-2,0],20),
    ([1,1,3,5],2), ([4,4,3,5],8)])
spec(684, '非空 ASCII 字符串 str 和单个字符 x；把 str 无限重复，统计前10个字符中 x 出现次数。', [
    (['a','a'],10), (['b','a'],0), (['ab','a'],5), (['abc','c'],3),
    (['abcdefghijk','k'],0), (['abc','a'],4)])
spec(685, '整数 0<=n<=100；返回闭区间 [1,n] 内所有素数之和。', [
    ([0],0), ([1],0), ([2],2), ([3],5), ([4],5), ([6],10)])
spec(711, '整数 0<=n<=10**9；个位算第1位，比较奇数位数字乘积与偶数位数字乘积；不足两位返回False。', [
    ([0],False), ([7],False), ([11],True), ([12],False), ([100],True), ([121],False)])
spec(714, '整数 1<=n<=10**6；将n分解为互不相同的素数幂的乘积，返回最多能有多少个因子；n=1返回0。', [
    ([1],0), ([2],1), ([8],2), ([16],2), ([32],2), ([64],3)])
spec(751, '整数数组，长度<=30，i=0；检查完整二叉树数组表示是否满足每个父节点<=子节点，允许空数组。', [
    ([[],0],True), ([[5],0],True), ([[2,1],0],False), ([[1,2],0],True),
    ([[1,1,1],0],True), ([[1,3,2,0],0],False)])
spec(752, '整数 1<=n<=12；Jacobsthal数满足J0=0、J1=1、Jn=J(n-1)+2*J(n-2)，返回Jn。', [
    ([1],1), ([3],3), ([6],21), ([7],43), ([8],85), ([9],171)])
spec(762, '整数月份1..12；月份为4、6、9、11时返回True，否则False。', [
    ([1],False), ([3],False), ([4],True), ([9],True), ([10],False), ([11],True)])
spec(764, 'ASCII 字符串，允许空串；只统计字符0..9的出现数量。', [
    ([''],0), (['abc'],0), (['0'],1), (['9'],1), (['a1b2c3'],3), (['-12.50'],4)])
spec(768, '整数0<=x<=10**9；二进制表示中1的个数为奇数时返回True；x=0返回False。', [
    ([0],False), ([1],True), ([2],True), ([3],False), ([7],True), ([15],False)])
spec(770, '整数0<=n<=8；返回前n个正奇数的四次方之和。', [
    ([0],0), ([1],1), ([5],9669), ([6],24310), ([7],52871), ([8],103496)])
spec(777, '非空整数数组，n=len(arr)<=30；每个不同的值只计一次，返回这些值的和；输入修改允许。', [
    ([[1],1],1), ([[2,2],2],2), ([[1,1,2,2],4],3), ([[0,-1,-1],3],-1),
    ([[3,2,1],3],6), ([[-2,5,-2],3],3)],
    'Upstream wording non-repeated is ambiguous; its assertions specify summing distinct values, not frequency-one values. Contract makes this explicit.')
spec(782, '整数数组，长度<=20，允许空数组；返回所有奇数长度连续子数组的元素和之和。', [
    ([[]],0), ([[5]],5), ([[1,2]],3), ([[1,1,1]],6),
    ([[1,1,1,1]],10), ([[-1,0,1]],0)])
spec(803, '正整数1<=n<=1000；是完全平方数则返回True，否则False；本任务不定义零或负数输入。', [
    ([1],True), ([2],False), ([4],True), ([9],True), ([15],False), ([25],True)],
    'Explicit bounded positive-integer repair task; no claim about original implementation at zero or negative inputs.')
spec(804, '整数数组，n=len(arr)<=30；存在偶数时积为偶数，返回True；空数组的积约定为1，返回False。', [
    ([[],0],False), ([[1],1],False), ([[2],1],True), ([[0],1],True),
    ([[-3,-5],2],False), ([[-3,-2],2],True)])
spec(815, '数组元素只含0、1、2，n=len(arr)<=30；返回非递减排列，允许空数组和原地修改。', [
    ([[],0],[]), ([[0],1],[0]), ([[2,0],2],[0,2]), ([[2,1,0],3],[0,1,2]),
    ([[1,1,1],3],[1,1,1]), ([[2,2,0,0],4],[0,0,2,2])])
spec(837, '整数0<=n<=8；返回前n个正奇数的立方和。', [
    ([0],0), ([1],1), ([5],1225), ([6],2556), ([7],4753), ([8],8128)])
spec(842, '整数数组，arr_size=len(arr)<=30；返回最先在原数组出现且总频次为奇数的值，没有则返回-1。', [
    ([[],0],-1), ([[2],1],2), ([[2,2],2],-1), ([[2,2,3],3],3),
    ([[4,5],2],4), ([[0,0,-3,-3,-3],5],-3)])
spec(844, '整数1<=n<=30、1<=k<=n；把1..n按奇数递增在前、偶数递增在后排列，返回第k个值。', [
    ([1,1],1), ([2,1],1), ([2,2],2), ([5,3],5), ([5,4],2), ([6,6],6)])
spec(849, '整数1<=N<=100；返回所有不同素因子的和，每个素因子只计一次，N=1返回0。', [
    ([1],0), ([2],2), ([4],2), ([6],5), ([30],10), ([49],7)])
spec(863, '非空整数数组，n=len(arr)<=30；忽略重复值和原顺序，返回最长连续整数集合的长度；允许修改输入。', [
    ([[1],1],1), ([[2,2],2],1), ([[3,1,2],3],3), ([[0,-1,1,5],4],3),
    ([[10,20],2],1), ([[5,4,3,3,2],5],4)])
spec(867, '整数数组，n=len(arr)<=30；返回使元素和成为偶数的最小严格正整数加数，和为奇数时1、偶数时2。', [
    ([[],0],2), ([[0],1],2), ([[1],1],1), ([[-1],1],1),
    ([[2,4],2],2), ([[2,3],2],1)],
    'Strictly positive addend is specified explicitly to match upstream assertions; zero is not an allowed addend.')
spec(868, 'ASCII 字符串，以普通空格分词，首尾空白可忽略；返回最后一个词长度，无词返回0。', [
    (['a'],1), (['  '],0), (['a b'],1), ([' hi  world  '],5),
    (['ab   cdef'],4), (['  abc'],3)])
spec(871, '两个ASCII字符串，允许空串；判断第二个是否能由第一个循环旋转得到，空串互为旋转。', [
    (['',''],True), (['a','a'],True), (['ab','ba'],True), (['ab','ab'],True),
    (['ab','a'],False), (['abc','acb'],False)])
spec(874, '两个ASCII字符串str1和非空str2；str1是否由str2重复整数次组成，允许重复0次得到空串。', [
    (['','a'],True), (['a','a'],True), (['aa','a'],True), (['ab','ab'],True),
    (['abab','ab'],True), (['abac','ab'],False)])
spec(876, '正整数1<=x,y<=100；返回最小公倍数。', [
    ([1,1],1), ([1,7],7), ([3,3],3), ([4,8],8), ([3,5],15), ([6,10],30)])
spec(880, '整数a,b,c，a非零、绝对值<=100；按判别式返回实根数量字符串：2 solutions、1 solution、No solutions。', [
    ([1,0,-1],'2 solutions'), ([1,0,0],'1 solution'), ([1,0,1],'No solutions'),
    ([1,-2,1],'1 solution'), ([2,0,-8],'2 solutions'), ([-1,0,-1],'No solutions')])
spec(885, '两个ASCII字符串，长度<=30；是否存在字符间一一映射使第一串逐位变为第二串，允许空串。', [
    (['',''],True), (['a','b'],True), (['aa','bc'],False), (['ab','cc'],False),
    (['aba','xyx'],True), (['a',''],False)])
spec(890, '严格递增整数数组arr1、arr2；arr1由arr2插入一个额外值形成，n=len(arr2)<=30，返回额外值在arr1的下标。', [
    ([[1],[],0],0), ([[1,2],[2],1],0), ([[1,2],[1],1],1), ([[1,2,3],[1,3],2],1),
    ([[0,1,2,3],[0,1,2],3],3), ([[-2,0,2],[-2,2],2],1)])
spec(895, '非空整数数组，长度<=30；选择至少一个元素，选取下标两两不相邻，返回最大元素和。', [
    ([[5]],5), ([[1,2]],2), ([[2,1,2]],4), ([[-2,-1,-3]],-1),
    ([[0,0,0]],0), ([[5,1,1,5]],10)])
spec(901, '整数1<=n<=13；返回可被1..n所有正整数整除的最小正整数。', [
    ([3],6), ([4],12), ([5],60), ([6],60), ([7],420), ([8],840)])
spec(903, '整数0<=n<=100；统计1..n所有数的无前导零二进制表示中0的总数量，n=0返回0。', [
    ([0],0), ([1],0), ([3],1), ([4],3), ([6],5), ([7],5)])
spec(909, '整数2<=num<=2000；返回严格小于num的最大正十进制回文数。', [
    ([2],1), ([10],9), ([11],9), ([12],11), ([100],99), ([101],99)])
spec(914, '长度2..30的ASCII字符串；恰好两个不同字符交替出现返回True，其他情况False。', [
    (['ab'],True), (['aa'],False), (['aba'],True), (['abba'],False),
    (['121212'],True), (['aAaA'],True)])
spec(923, 'ASCII字符串X、Y，长度各<=7，m=len(X)、n=len(Y)；返回最短公共超序列长度，允许空串。', [
    (['','',0,0],0), (['','a',0,1],1), (['a','a',1,1],1), (['a','b',1,1],2),
    (['ab','ba',2,2],3), (['abc','abc',3,3],3)])
spec(934, '整数0<=n,m<=5；从(0,0)到(n,m)每步向右、向上或右上，返回路径数Delannoy(n,m)。', [
    ([0,0],1), ([0,3],1), ([1,1],3), ([1,2],5), ([2,2],13), ([2,3],25)])
spec(952, '整数0<=r<=n<=30、2<=p<=100；返回二项式系数C(n,r)模p，p不要求为素数。', [
    ([0,0,2],1), ([1,0,3],1), ([1,1,3],1), ([4,2,5],1),
    ([5,2,7],3), ([6,3,8],4)])
spec(971, '整数0<=n<=30，段长a,b,c均为1..30；必须完全分割长度n，返回最多段数，无法分割返回-1。', [
    ([0,2,3,4],0), ([1,2,3,4],-1), ([4,2,3,5],2), ([5,2,3,4],2),
    ([6,2,3,4],3), ([7,2,4,6],-1)])
spec(973, 'ASCII字符串，0<=d<=len(s)<=30；返回左旋d个字符的结果，允许空串。', [
    (['',0],''), (['a',0],'a'), (['a',1],'a'), (['abc',0],'abc'),
    (['abc',3],'abc'), (['abcd',1],'bcda')])
spec(974, '非空整数三角形，第i行有i+1项，行数<=8；从顶到底每次取下一行相邻下标，返回最小路径和。', [
    ([[[5]]],5), ([[[1],[2,3]]],3), ([[[0],[-1,-2],[3,4,-5]]],-7),
    ([[[2],[3,4],[6,5,7],[4,1,8,3]]],11), ([[[-1],[2,3],[1,-1,-3]]],-1),
    ([[[0],[0,0],[0,0,0]]],0)])

REVIEW_EXCLUSIONS = {
    665: 'Moves every occurrence of the first value; not a single-element rotation for duplicate inputs.',
    692: 'Returns None at n>=10 although last two factorial digits should be 00.',
    733: 'One upstream assertion uses an unsorted array, contradicting the sorted-array domain.',
    743: 'Different slice offsets duplicate/drop elements; not a consistent right rotation.',
    755: 'Crashes for lists with >=3 identical values instead of handling missing second distinct value.',
    757: 'Counts self-palindromes and returns string; reverse-pair convention is insufficiently specified.',
    775: 'Checks even positions as well as odd positions, stronger than the stated odd-position predicate.',
    776: 'Neighbor-vowel semantics and short-string handling require further contract review.',
    793: 'Upstream third assertion is unsorted and n exceeds list length.',
    802: 'First descent is not a valid rotation count on the supplied reverse-sorted example.',
    806: 'Returns last uppercase run rather than the maximum run.',
    826: 'Right-triangle branch compares a squared side with itself plus another squared side.',
    850: 'Known same triangle-angle predicate as existing train source 677; omit semantic duplicate.',
    866: 'Misspells August as Augest, failing a standard month name.',
}
