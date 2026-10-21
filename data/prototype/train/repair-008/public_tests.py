"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import rotate_left


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = rotate_left(*[[1, 2, 3], 1])
        expected = [2, 3, 1]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = rotate_left(*[[], 7])
        expected = []
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
