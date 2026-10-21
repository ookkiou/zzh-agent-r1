import unittest
from solution import find_first_duplicate

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_first_duplicate(*[[1, 2, 3, 4, 4, 5]])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_first_duplicate(*[[1, 2, 3, 4]])
        expected = -1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

