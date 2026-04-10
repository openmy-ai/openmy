#!/usr/bin/env python3
import unittest

from openmy.domain.models import ScreenSession
from openmy.services.screen_recognition.privacy import apply_privacy_filters
from openmy.services.screen_recognition.settings import ScreenContextSettings


class TestScreenPrivacy(unittest.TestCase):
    def make_session(self, **overrides):
        payload = {
            "app_name": "Google Chrome",
            "window_name": "OpenMy - Cursor",
            "url_domain": "openmy.app",
            "text": "正在修改 OpenMy 的屏幕上下文主链",
            "summary": "",
            "start_time": "2026-04-10T10:00:00+08:00",
            "end_time": "2026-04-10T10:05:00+08:00",
        }
        payload.update(overrides)
        return ScreenSession(**payload)

    def test_default_summary_only_redacts_sensitive_secret_patterns(self):
        sessions = [
            self.make_session(
                window_name=".env - Cursor",
                text="OPENAI_API_KEY=sk-secret-value\nANTHROPIC_API_KEY=ak-secret-value",
            )
        ]
        filtered = apply_privacy_filters(
            sessions,
            ScreenContextSettings(enabled=True, participation_mode="summary_only"),
        )

        self.assertEqual(len(filtered), 1)
        self.assertTrue(filtered[0].sensitive)
        self.assertTrue(filtered[0].summary_only)
        self.assertEqual(filtered[0].text, "")
        self.assertIn("敏感", filtered[0].privacy_reason)

    def test_payment_and_address_context_are_summary_only(self):
        sessions = [
            self.make_session(
                app_name="支付宝",
                window_name="订单支付",
                url_domain="alipay.com",
                text="收货地址：上海市徐汇区 xx 路 188 号，手机号 13800138000",
            )
        ]
        filtered = apply_privacy_filters(
            sessions,
            ScreenContextSettings(enabled=True, participation_mode="full"),
        )

        self.assertTrue(filtered[0].sensitive)
        self.assertTrue(filtered[0].summary_only)
        self.assertEqual(filtered[0].text, "")

    def test_chat_privacy_is_redacted_to_summary_only(self):
        sessions = [
            self.make_session(
                app_name="微信",
                window_name="和妈妈聊天",
                text="妈妈：身份证号 3101xxxxxxxxxx，验证码 556677",
            )
        ]
        filtered = apply_privacy_filters(
            sessions,
            ScreenContextSettings(enabled=True, participation_mode="summary_only"),
        )

        self.assertTrue(filtered[0].sensitive)
        self.assertTrue(filtered[0].summary_only)
        self.assertEqual(filtered[0].text, "")

    def test_exclude_rules_drop_matching_apps_domains_and_windows(self):
        sessions = [
            self.make_session(app_name="微信"),
            self.make_session(url_domain="aliyun.com"),
            self.make_session(window_name="密码与钥匙串"),
        ]
        filtered = apply_privacy_filters(
            sessions,
            ScreenContextSettings(
                enabled=True,
                participation_mode="full",
                exclude_apps=["微信"],
                exclude_domains=["aliyun.com"],
                exclude_window_keywords=["钥匙串"],
            ),
        )

        self.assertEqual(filtered, [])


if __name__ == "__main__":
    unittest.main()
