"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import middle_item


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = middle_item(*[[4, 5, 6]])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = middle_item(*[[9]])
        expected = 9
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
