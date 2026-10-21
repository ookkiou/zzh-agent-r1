import unittest
from solution import perfect_squares

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = perfect_squares(*[1, 30])
        expected = [1, 4, 9, 16, 25]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = perfect_squares(*[50, 100])
        expected = [64, 81, 100]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

