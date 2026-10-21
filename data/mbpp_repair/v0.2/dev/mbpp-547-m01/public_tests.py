import unittest
from solution import Total_Hamming_Distance

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = Total_Hamming_Distance(*[4])
        expected = 7
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = Total_Hamming_Distance(*[2])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

