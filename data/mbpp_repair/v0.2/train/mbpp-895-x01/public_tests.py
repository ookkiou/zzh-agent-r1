import unittest
from solution import max_sum_subseq

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = max_sum_subseq(*[[1, 2, 9, 4, 5, 0, 4, 11, 6]])
        expected = 26
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = max_sum_subseq(*[[1, 2, 9, 5, 6, 0, 5, 12, 7]])
        expected = 28
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

