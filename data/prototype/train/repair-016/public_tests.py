"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import is_leap_year


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = is_leap_year(*[2000])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = is_leap_year(*[1900])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
