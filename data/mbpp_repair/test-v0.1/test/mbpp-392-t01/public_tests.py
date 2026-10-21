import unittest
from solution import get_max_sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = get_max_sum(*[60])
        expected = 106
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = get_max_sum(*[10])
        expected = 12
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

