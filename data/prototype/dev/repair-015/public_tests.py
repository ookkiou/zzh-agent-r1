"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import count_runs


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_runs(*[[1, 1, 2, 1]])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_runs(*[[]])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
