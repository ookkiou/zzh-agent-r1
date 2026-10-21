"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import unique_in_order


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = unique_in_order(*[[1, 2, 1, 3]])
        expected = [1, 2, 3]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = unique_in_order(*[[]])
        expected = []
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
