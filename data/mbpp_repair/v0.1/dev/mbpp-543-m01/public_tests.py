import unittest
from solution import count_digits

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_digits(*[9875, 10])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_digits(*[98759853034, 100])
        expected = 11
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

