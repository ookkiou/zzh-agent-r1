import unittest
from solution import find_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_Sum(*[[1, 2, 3, 1, 1, 4, 5, 6], 8])
        expected = 21
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_Sum(*[[1, 10, 9, 4, 2, 10, 10, 45, 4], 9])
        expected = 71
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

