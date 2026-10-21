import unittest
from solution import sum_Of_Series

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_Of_Series(*[5])
        expected = 225
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_Of_Series(*[2])
        expected = 9
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

