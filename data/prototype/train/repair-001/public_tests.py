"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import count_at_least


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_at_least(*[[2, 3, 4], 3])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_at_least(*[[], 5])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
