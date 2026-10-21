import unittest
from solution import product_Equal

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = product_Equal(*[2841])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = product_Equal(*[1234])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

