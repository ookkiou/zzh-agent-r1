import unittest
from solution import common_element

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = common_element(*[[1, 2, 3, 4, 5], [5, 6, 7, 8, 9]])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = common_element(*[[1, 2, 3, 4, 5], [6, 7, 8, 9]])
        expected = None
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

