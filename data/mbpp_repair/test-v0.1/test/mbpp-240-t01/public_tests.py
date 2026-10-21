import unittest
from solution import replace_list

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = replace_list(*[[1, 3, 5, 7, 9, 10], [2, 4, 6, 8]])
        expected = [1, 3, 5, 7, 9, 2, 4, 6, 8]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = replace_list(*[[1, 2, 3, 4, 5], [5, 6, 7, 8]])
        expected = [1, 2, 3, 4, 5, 6, 7, 8]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

