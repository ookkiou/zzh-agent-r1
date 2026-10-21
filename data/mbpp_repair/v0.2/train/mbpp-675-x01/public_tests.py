import unittest
from solution import sum_nums

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_nums(*[2, 10, 11, 20])
        expected = 20
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_nums(*[15, 17, 1, 10])
        expected = 32
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

