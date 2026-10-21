import unittest
from solution import min_sum_path

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = min_sum_path(*[[[2], [3, 9], [1, 6, 7]]])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = min_sum_path(*[[[2], [3, 7], [8, 5, 6]]])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

