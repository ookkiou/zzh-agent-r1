import unittest
from solution import get_Min_Squares

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = get_Min_Squares(*[6])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = get_Min_Squares(*[2])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

