import unittest
from solution import max_product

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = max_product(*[[3, 100, 4, 5, 150, 6], 6])
        expected = 45000
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = max_product(*[[4, 42, 55, 68, 80], 5])
        expected = 50265600
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

