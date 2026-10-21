import unittest
from solution import permutation_coefficient

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = permutation_coefficient(*[10, 2])
        expected = 90
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = permutation_coefficient(*[10, 3])
        expected = 720
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

