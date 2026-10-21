"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import product


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = product(*[[2, 3]])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = product(*[[]])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
