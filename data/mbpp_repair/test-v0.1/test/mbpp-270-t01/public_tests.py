import unittest
from solution import sum_even_and_even_index

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_even_and_even_index(*[[5, 6, 12, 1, 18, 8], 6])
        expected = 30
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_even_and_even_index(*[[3, 20, 17, 9, 2, 10, 18, 13, 6, 18], 10])
        expected = 26
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

