import unittest
from solution import int_to_roman

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = int_to_roman(*[1])
        expected = 'I'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = int_to_roman(*[50])
        expected = 'L'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

