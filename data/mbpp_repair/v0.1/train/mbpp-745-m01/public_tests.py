import unittest
from solution import divisible_by_digits

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = divisible_by_digits(*[1, 22])
        expected = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15, 22]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = divisible_by_digits(*[1, 15])
        expected = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

