"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import valid_port


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = valid_port(*[0])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = valid_port(*[8080])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
