import unittest
from solution import is_Product_Even

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = is_Product_Even(*[[1, 2, 3], 3])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = is_Product_Even(*[[1, 2, 1, 4], 4])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

