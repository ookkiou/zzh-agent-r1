import unittest
from solution import max_profit

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = max_profit(*[[1, 5, 2, 3, 7, 6, 4, 5], 3])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = max_profit(*[[2, 4, 7, 5, 4, 3, 5], 2])
        expected = 7
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

