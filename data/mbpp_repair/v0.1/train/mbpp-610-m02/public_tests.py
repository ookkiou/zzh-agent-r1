import unittest
from solution import remove_kth_element

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = remove_kth_element(*[[1, 1, 2, 3, 4, 4, 5, 1], 3])
        expected = [1, 1, 3, 4, 4, 5, 1]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = remove_kth_element(*[[0, 0, 1, 2, 3, 4, 4, 5, 6, 6, 6, 7, 8, 9, 4, 4], 4])
        expected = [0, 0, 1, 3, 4, 4, 5, 6, 6, 6, 7, 8, 9, 4, 4]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

