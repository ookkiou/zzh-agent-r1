import unittest
from solution import sum_digits

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_digits(*[345])
        expected = 12
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_digits(*[12])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

