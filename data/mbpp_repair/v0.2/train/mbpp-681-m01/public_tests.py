import unittest
from solution import smallest_Divisor

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = smallest_Divisor(*[10])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = smallest_Divisor(*[25])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

