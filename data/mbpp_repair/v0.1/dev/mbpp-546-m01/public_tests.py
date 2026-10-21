import unittest
from solution import last_occurence_char

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = last_occurence_char(*['hello world', 'l'])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = last_occurence_char(*['language', 'g'])
        expected = 7
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

