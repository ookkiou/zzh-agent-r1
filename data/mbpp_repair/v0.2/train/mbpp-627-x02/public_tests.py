import unittest
from solution import find_First_Missing

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_First_Missing(*[[0, 1, 2, 3], 0, 3])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_First_Missing(*[[0, 1, 2, 6, 9], 0, 4])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

