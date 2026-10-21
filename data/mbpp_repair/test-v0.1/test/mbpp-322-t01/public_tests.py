import unittest
from solution import position_min

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = position_min(*[[12, 33, 23, 10, 67, 89, 45, 667, 23, 12, 11, 10, 54]])
        expected = [3, 11]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = position_min(*[[1, 2, 2, 2, 4, 4, 4, 5, 5, 5, 5]])
        expected = [0]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

