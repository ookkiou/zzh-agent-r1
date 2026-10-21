import unittest
from solution import first_repeated_char

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = first_repeated_char(*['abcabc'])
        expected = 'a'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = first_repeated_char(*['abc'])
        expected = 'None'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

