import unittest

from self_healing.sandbox.logs import filter_relevant_logs


class LogFilterTests(unittest.TestCase):
    def test_keeps_error_context_and_truncates_noise(self):
        logs = "\n".join([f"noise {i}" for i in range(20)] + ["E AssertionError: bad value"] + [f"tail {i}" for i in range(20)])
        filtered = filter_relevant_logs(logs, context_lines=2)
        self.assertIn("AssertionError", filtered)
        self.assertIn("noise 19", filtered)
        self.assertIn("tail 1", filtered)
        self.assertNotIn("noise 0", filtered)


if __name__ == "__main__":
    unittest.main()
