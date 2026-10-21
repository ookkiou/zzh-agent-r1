import unittest
from solution import last_Digit_Factorial

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = last_Digit_Factorial(*[4])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = last_Digit_Factorial(*[21])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

