"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import within_limit


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = within_limit(*[10, 10])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = within_limit(*[11, 10])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
