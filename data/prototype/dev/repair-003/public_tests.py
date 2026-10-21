"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import ticket_category


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = ticket_category(*[18])
        expected = 'adult'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = ticket_category(*[10])
        expected = 'child'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
