import unittest
from solution import two_unique_nums

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = two_unique_nums(*[[1, 2, 3, 2, 3, 4, 5]])
        expected = [1, 4, 5]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = two_unique_nums(*[[1, 2, 3, 2, 4, 5]])
        expected = [1, 3, 4, 5]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

