import unittest
from solution import roman_to_int

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = roman_to_int(*['MMMCMLXXXVI'])
        expected = 3986
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = roman_to_int(*['MMMM'])
        expected = 4000
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

