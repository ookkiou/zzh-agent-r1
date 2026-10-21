import unittest
from solution import first_Element

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = first_Element(*[[0, 1, 2, 3, 4, 5], 6, 1])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = first_Element(*[[1, 2, 1, 3, 4], 5, 2])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

