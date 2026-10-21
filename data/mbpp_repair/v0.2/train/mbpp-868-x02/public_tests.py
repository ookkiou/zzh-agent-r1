import unittest
from solution import length_Of_Last_Word

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = length_Of_Last_Word(*['python language'])
        expected = 8
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = length_Of_Last_Word(*['PHP'])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

