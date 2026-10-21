import unittest
from solution import empty_list

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = empty_list(*[5])
        expected = [{}, {}, {}, {}, {}]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = empty_list(*[6])
        expected = [{}, {}, {}, {}, {}, {}]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

