import unittest
from solution import max_sub_array_sum_repeated

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = max_sub_array_sum_repeated(*[[10, 20, -30, -1], 4, 3])
        expected = 30
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = max_sub_array_sum_repeated(*[[-1, 10, 20], 3, 2])
        expected = 59
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

