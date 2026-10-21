import unittest
from solution import get_odd_occurence

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = get_odd_occurence(*[[2, 3, 5, 4, 5, 2, 4, 3, 5, 2, 4, 4, 2], 13])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = get_odd_occurence(*[[1, 2, 3, 2, 3, 1, 3], 7])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

