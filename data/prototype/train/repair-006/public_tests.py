"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import tail_items


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = tail_items(*[[1, 2, 3], 0])
        expected = []
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = tail_items(*[[1, 2, 3], 2])
        expected = [2, 3]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
