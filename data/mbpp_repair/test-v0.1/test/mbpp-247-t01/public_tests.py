import unittest
from solution import lps

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = lps(*['TENS FOR TENS'])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = lps(*['CARDIO FOR CARDS'])
        expected = 7
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

