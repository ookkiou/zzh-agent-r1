"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import parse_bool


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = parse_bool(*['false'])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = parse_bool(*['YES'])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
