import unittest
from solution import find_longest_conseq_subseq

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_longest_conseq_subseq(*[[1, 2, 2, 3], 4])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_longest_conseq_subseq(*[[1, 9, 3, 10, 4, 20, 2], 7])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

