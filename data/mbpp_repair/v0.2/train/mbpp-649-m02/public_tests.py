import unittest
from solution import sum_Range_list

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_Range_list(*[[2, 1, 5, 6, 8, 3, 4, 9, 10, 11, 8, 12], 8, 10])
        expected = 29
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_Range_list(*[[1, 2, 3, 4, 5], 1, 2])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

