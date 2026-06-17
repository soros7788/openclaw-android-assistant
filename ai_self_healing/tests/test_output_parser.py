import unittest

from self_healing.healer.output_parser import clean_model_code_output


class OutputParserTests(unittest.TestCase):
    def test_strips_markdown_fence(self):
        text = "```python\nprint('ok')\n```"
        self.assertEqual(clean_model_code_output(text), "print('ok')\n")

    def test_preserves_plain_code_with_newline(self):
        self.assertEqual(clean_model_code_output("x = 1"), "x = 1\n")


if __name__ == "__main__":
    unittest.main()
