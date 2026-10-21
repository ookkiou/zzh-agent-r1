import unittest
from solution import first_non_repeating_character

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = first_non_repeating_character(*['abcabc'])
        expected = None
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = first_non_repeating_character(*['abc'])
        expected = 'a'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

