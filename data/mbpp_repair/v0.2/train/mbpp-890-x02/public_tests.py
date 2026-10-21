import unittest
from solution import find_Extra

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_Extra(*[[1, 2, 3, 4], [1, 2, 3], 3])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_Extra(*[[2, 4, 6, 8, 10], [2, 4, 6, 8], 4])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

