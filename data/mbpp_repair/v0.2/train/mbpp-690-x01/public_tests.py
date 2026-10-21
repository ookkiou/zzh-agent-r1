import unittest
from solution import mul_consecutive_nums

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = mul_consecutive_nums(*[[1, 1, 3, 4, 4, 5, 6, 7]])
        expected = [1, 3, 12, 16, 20, 30, 42]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = mul_consecutive_nums(*[[4, 5, 8, 9, 6, 10]])
        expected = [20, 40, 72, 54, 60]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

