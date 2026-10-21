import unittest
from solution import swap_List

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = swap_List(*[[1, 2, 3]])
        expected = [3, 2, 1]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = swap_List(*[[1, 2, 3, 4, 4]])
        expected = [4, 2, 3, 4, 1]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

