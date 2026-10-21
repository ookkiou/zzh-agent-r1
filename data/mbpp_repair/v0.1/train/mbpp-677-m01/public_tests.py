import unittest
from solution import validity_triangle

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = validity_triangle(*[60, 50, 90])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = validity_triangle(*[45, 75, 60])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

