"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import ranges_overlap


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = ranges_overlap(*[1, 3, 3, 5])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = ranges_overlap(*[1, 2, 4, 5])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
