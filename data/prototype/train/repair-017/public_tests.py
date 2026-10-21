"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import safe_divide


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = safe_divide(*[4, 0])
        expected = None
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = safe_divide(*[5, 2])
        expected = 2.5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
