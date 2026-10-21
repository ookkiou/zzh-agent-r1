import unittest
from solution import is_subset

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = is_subset(*[[11, 1, 13, 21, 3, 7], 6, [11, 3, 7, 1], 4])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = is_subset(*[[1, 2, 3, 4, 5, 6], 6, [1, 2, 4], 3])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

