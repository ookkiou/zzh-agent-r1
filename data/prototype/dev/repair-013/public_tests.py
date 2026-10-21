"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import sum_positive


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_positive(*[[-1, 0, 2, 3]])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_positive(*[[]])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
