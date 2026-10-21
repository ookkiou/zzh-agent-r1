import unittest
from solution import compute_Last_Digit

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = compute_Last_Digit(*[2, 4])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = compute_Last_Digit(*[6, 8])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

