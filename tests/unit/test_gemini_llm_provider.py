#!/usr/bin/env python3
import unittest
from unittest.mock import patch


class TestGeminiLLMProvider(unittest.TestCase):
    @patch("openmy.providers.llm.gemini.genai.Client")
    def test_generate_text_omits_empty_config(self, client_cls):
        from openmy.providers.llm.gemini import GeminiLLMProvider

        client = client_cls.return_value
        client.models.generate_content.return_value.text = "ok"

        provider = GeminiLLMProvider(api_key="test-key", model="gemini-test")
        result = provider.generate_text(task="role inference", prompt="hello")

        self.assertEqual(result, "ok")
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-test")
        self.assertEqual(kwargs["contents"], "hello")
        self.assertNotIn("config", kwargs)


if __name__ == "__main__":
    unittest.main()
