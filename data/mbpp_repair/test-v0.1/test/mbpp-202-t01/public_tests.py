import unittest
from solution import remove_even

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = remove_even(*['python'])
        expected = 'pto'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = remove_even(*['program'])
        expected = 'porm'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

