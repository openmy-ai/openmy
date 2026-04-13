#!/usr/bin/env python3
import io
import os
import unittest


class TtyStringIO(io.StringIO):
    def isatty(self) -> bool:  # pragma: no cover - tiny helper
        return True


class TestInteractiveHelpers(unittest.TestCase):
    def test_select_option_arrow_mode_uses_key_reader(self):
        from openmy.utils.interactive import select_option

        output = TtyStringIO()
        keys = iter(["down", "enter"])
        selected = select_option(
            "选一个",
            ["甲", "乙", "丙"],
            output=output,
            key_reader=lambda: next(keys),
        )

        self.assertEqual(selected, 1)
        self.assertIn("选一个", output.getvalue())

    def test_select_option_fallback_uses_number_input(self):
        from openmy.utils.interactive import select_option

        output = io.StringIO()
        answers = iter(["2"])
        selected = select_option(
            "选一个",
            ["甲", "乙", "丙"],
            output=output,
            input_fn=lambda _prompt: next(answers),
            platform_name="win32",
        )

        self.assertEqual(selected, 1)
        self.assertIn("1. 甲", output.getvalue())

    def test_prompt_input_and_dragged_path_cleanup(self):
        from openmy.utils.interactive import prompt_input, strip_dragged_path

        output = io.StringIO()
        value = prompt_input("标题", "提示", input_fn=lambda _prompt: " '~/Desktop/test file.wav' ", output=output)

        self.assertEqual(strip_dragged_path(value), os.path.expanduser("~/Desktop/test file.wav"))
        self.assertIn("标题", output.getvalue())


if __name__ == "__main__":
    unittest.main()
