import unittest
from solution import is_abundant

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = is_abundant(*[12])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = is_abundant(*[13])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

