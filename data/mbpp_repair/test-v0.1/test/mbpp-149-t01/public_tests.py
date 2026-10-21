import unittest
from solution import longest_subseq_with_diff_one

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = longest_subseq_with_diff_one(*[[1, 2, 3, 4, 5, 3, 2], 7])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = longest_subseq_with_diff_one(*[[10, 9, 4, 5, 4, 8, 6], 7])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

