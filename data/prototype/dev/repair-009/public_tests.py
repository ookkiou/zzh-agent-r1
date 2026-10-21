"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import every_other


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = every_other(*[[1, 2, 3, 4]])
        expected = [1, 3]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = every_other(*[[]])
        expected = []
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
