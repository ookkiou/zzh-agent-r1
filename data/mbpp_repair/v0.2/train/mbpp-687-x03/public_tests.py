import unittest
from solution import recur_gcd

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = recur_gcd(*[12, 14])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = recur_gcd(*[13, 17])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

