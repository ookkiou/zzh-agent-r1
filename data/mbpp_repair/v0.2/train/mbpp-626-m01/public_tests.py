import unittest
from solution import triangle_area

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = triangle_area(*[0])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = triangle_area(*[-1])
        expected = -1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

