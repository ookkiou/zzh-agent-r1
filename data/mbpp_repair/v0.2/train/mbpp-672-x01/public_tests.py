import unittest
from solution import max_of_three

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = max_of_three(*[10, 20, 30])
        expected = 30
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = max_of_three(*[55, 47, 39])
        expected = 55
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

