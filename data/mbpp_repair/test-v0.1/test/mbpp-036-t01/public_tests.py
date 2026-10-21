import unittest
from solution import find_Nth_Digit

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_Nth_Digit(*[1, 2, 1])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_Nth_Digit(*[3, 5, 1])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

