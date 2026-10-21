import unittest
from solution import previous_palindrome

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = previous_palindrome(*[99])
        expected = 88
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = previous_palindrome(*[1221])
        expected = 1111
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

