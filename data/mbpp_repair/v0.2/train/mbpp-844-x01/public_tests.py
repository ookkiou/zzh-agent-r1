import unittest
from solution import get_Number

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = get_Number(*[8, 5])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = get_Number(*[7, 2])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

