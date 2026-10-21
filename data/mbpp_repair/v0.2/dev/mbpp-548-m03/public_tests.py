import unittest
from solution import longest_increasing_subsequence

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = longest_increasing_subsequence(*[[10, 22, 9, 33, 21, 50, 41, 60]])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = longest_increasing_subsequence(*[[3, 10, 2, 1, 20]])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

