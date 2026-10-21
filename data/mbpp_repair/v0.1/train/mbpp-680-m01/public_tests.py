import unittest
from solution import increasing_trend

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = increasing_trend(*[[1, 2, 3, 4]])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = increasing_trend(*[[4, 3, 2, 1]])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

