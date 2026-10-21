import unittest
from solution import sum_Square

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_Square(*[25])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_Square(*[24])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

