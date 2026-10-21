import unittest
from solution import pair_OR_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = pair_OR_Sum(*[[5, 9, 7, 6], 4])
        expected = 47
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = pair_OR_Sum(*[[7, 3, 5], 3])
        expected = 12
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

