import unittest
from solution import find_missing

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_missing(*[[1, 2, 3, 5], 4])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_missing(*[[1, 3, 4, 5], 4])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

