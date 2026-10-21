import unittest
from solution import highest_Power_of_2

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = highest_Power_of_2(*[10])
        expected = 8
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = highest_Power_of_2(*[19])
        expected = 16
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

