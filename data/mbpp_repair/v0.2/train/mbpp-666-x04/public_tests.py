import unittest
from solution import count_char

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_char(*['Python', 'o'])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_char(*['little', 't'])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

