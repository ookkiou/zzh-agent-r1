import unittest
from solution import find_Min_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_Min_Sum(*[[3, 2, 1], [2, 1, 3], 3])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_Min_Sum(*[[1, 2, 3], [4, 5, 6], 3])
        expected = 9
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

