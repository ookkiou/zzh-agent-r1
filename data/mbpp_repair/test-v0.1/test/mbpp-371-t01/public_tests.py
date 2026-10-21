import unittest
from solution import smallest_missing

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = smallest_missing(*[[0, 1, 2, 3, 4, 5, 6], 0, 6])
        expected = 7
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = smallest_missing(*[[0, 1, 2, 6, 9, 11, 15], 0, 6])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

