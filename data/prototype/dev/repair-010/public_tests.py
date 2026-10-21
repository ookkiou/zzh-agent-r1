"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import prefix_items


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = prefix_items(*[[1, 2, 3], 2])
        expected = [1, 2]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = prefix_items(*[[1, 2], 0])
        expected = []
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
