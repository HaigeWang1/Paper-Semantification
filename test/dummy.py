import unittest


def multiplication(a, b):

    return a * b 

class Dummytest(unittest.TestCase):
    def test_dummy(self):

        self.assertEqual(3, multiplication(1,3))

if __name__ == "__main__":
    unittest.main()