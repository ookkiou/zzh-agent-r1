import unittest
from solution import max_path_sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = max_path_sum(*[[[1, 0, 0], [4, 8, 0], [1, 5, 3]], 2, 2])
        expected = 14
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = max_path_sum(*[[[13, 0, 0], [7, 4, 0], [2, 4, 6]], 2, 2])
        expected = 24
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

