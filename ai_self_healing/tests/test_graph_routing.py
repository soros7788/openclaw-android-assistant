import unittest

from self_healing.graph import route_after_verification


class GraphRoutingTests(unittest.TestCase):
    def test_routes_to_healer_when_not_fixed_and_budget_left(self):
        self.assertEqual(route_after_verification({"is_fixed": False, "exit_code": 1, "iterations": 0, "max_iterations": 2}), "healer")

    def test_ends_when_budget_exhausted(self):
        self.assertNotEqual(route_after_verification({"is_fixed": False, "exit_code": 1, "iterations": 2, "max_iterations": 2}), "healer")

    def test_ends_when_fixed(self):
        self.assertNotEqual(route_after_verification({"is_fixed": True, "exit_code": 0, "iterations": 0, "max_iterations": 2}), "healer")


if __name__ == "__main__":
    unittest.main()
