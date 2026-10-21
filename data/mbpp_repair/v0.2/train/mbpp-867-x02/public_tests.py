import unittest
from solution import min_Num

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = min_Num(*[[1, 2, 3, 4, 5, 6, 7, 8, 9], 9])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = min_Num(*[[1, 2, 3, 4, 5, 6, 7, 8], 8])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

