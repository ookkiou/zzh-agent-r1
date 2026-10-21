import unittest
from solution import count_even

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_even(*[[1, 2, 3, 5, 7, 8, 9, 10]])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_even(*[[10, 15, 14, 13, -18, 12, -20]])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

