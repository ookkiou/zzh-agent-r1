"""Visible debugging tests; private acceptance cases are not included."""
import unittest
from solution import shipping_cost


class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = shipping_cost(*[0])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = shipping_cost(*[50])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
