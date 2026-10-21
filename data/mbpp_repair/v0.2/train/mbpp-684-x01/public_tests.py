import unittest
from solution import count_Char

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_Char(*['abcac', 'a'])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_Char(*['abca', 'c'])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

