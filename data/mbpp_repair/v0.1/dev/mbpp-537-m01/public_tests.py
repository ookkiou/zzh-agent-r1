import unittest
from solution import first_repeated_word

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = first_repeated_word(*['ab ca bc ab'])
        expected = 'ab'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = first_repeated_word(*['ab ca bc'])
        expected = 'None'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

