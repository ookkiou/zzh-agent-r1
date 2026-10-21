import unittest
from solution import Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = Sum(*[60])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = Sum(*[39])
        expected = 16
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

