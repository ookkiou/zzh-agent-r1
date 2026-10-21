"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import max_value


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = max_value(*[[-5, -2, -8]])
        expected = -2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = max_value(*[[1, 4, 2]])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
