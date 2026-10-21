import unittest
from solution import maximum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = maximum(*[5, 10])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = maximum(*[-1, -2])
        expected = -1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

