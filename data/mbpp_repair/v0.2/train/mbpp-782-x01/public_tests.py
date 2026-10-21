import unittest
from solution import Odd_Length_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = Odd_Length_Sum(*[[1, 2, 4]])
        expected = 14
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = Odd_Length_Sum(*[[1, 2, 1, 2]])
        expected = 15
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

