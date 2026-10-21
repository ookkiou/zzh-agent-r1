import unittest
from solution import dif_Square

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = dif_Square(*[5])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = dif_Square(*[10])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

