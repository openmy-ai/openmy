#!/usr/bin/env python3
import unittest

from openmy.services.screen_recognition.provider import ScreenContextProvider
from openmy.services.screen_recognition.settings import ScreenContextSettings


class StubScreenClient:
    def __init__(self, available=True, events=None, elements=None, activity=None, boom=False):
        self.available = available
        self.events = list(events or [])
        self.elements = list(elements or [])
        self.activity = dict(activity or {})
        self.boom = boom
        self.calls = []

    def is_available(self):
        if self.boom:
            raise OSError("health failed")
        return self.available

    def search_ocr(self, start_time, end_time, app_name=None, limit=100):
        self.calls.append(("search_ocr", start_time, end_time, app_name, limit))
        if self.boom:
            raise OSError("ocr failed")
        return list(self.events)

    def search_elements(self, start_time, end_time, limit=50):
        self.calls.append(("search_elements", start_time, end_time, limit))
        if self.boom:
            raise OSError("elements failed")
        return list(self.elements)

    def activity_summary(self, start_time, end_time):
        self.calls.append(("activity_summary", start_time, end_time))
        if self.boom:
            raise OSError("activity failed")
        return dict(self.activity)


class TestScreenContextProvider(unittest.TestCase):
    def test_disabled_settings_short_circuit_provider(self):
        provider = ScreenContextProvider(
            client=StubScreenClient(available=True),
            settings=ScreenContextSettings(enabled=False, participation_mode="off"),
        )

        self.assertFalse(provider.is_enabled())
        self.assertFalse(provider.is_available())
        self.assertEqual(
            provider.fetch_ocr("2026-04-10T10:00:00+08:00", "2026-04-10T10:05:00+08:00"),
            [],
        )

    def test_health_check_respects_client(self):
        provider = ScreenContextProvider(
            client=StubScreenClient(available=True),
            settings=ScreenContextSettings(enabled=True, participation_mode="summary_only"),
        )
        self.assertTrue(provider.is_available())

    def test_provider_degrades_when_health_check_raises(self):
        provider = ScreenContextProvider(
            client=StubScreenClient(boom=True),
            settings=ScreenContextSettings(enabled=True, participation_mode="summary_only"),
        )
        self.assertFalse(provider.is_available())

    def test_fetch_ocr_returns_empty_on_client_error(self):
        provider = ScreenContextProvider(
            client=StubScreenClient(boom=True),
            settings=ScreenContextSettings(enabled=True, participation_mode="summary_only"),
        )

        events = provider.fetch_ocr(
            "2026-04-10T10:00:00+08:00",
            "2026-04-10T10:05:00+08:00",
            app_name="Cursor",
            limit=20,
        )

        self.assertEqual(events, [])

    def test_fetch_methods_delegate_when_available(self):
        client = StubScreenClient(
            available=True,
            events=[{"kind": "ocr"}],
            elements=[{"kind": "button"}],
            activity={"apps": [{"name": "Cursor", "minutes": 12}]},
        )
        provider = ScreenContextProvider(
            client=client,
            settings=ScreenContextSettings(enabled=True, participation_mode="full"),
        )

        self.assertEqual(
            provider.fetch_ocr("2026-04-10T10:00:00+08:00", "2026-04-10T10:05:00+08:00"),
            [{"kind": "ocr"}],
        )
        self.assertEqual(
            provider.fetch_elements("2026-04-10T10:00:00+08:00", "2026-04-10T10:05:00+08:00"),
            [{"kind": "button"}],
        )
        self.assertEqual(
            provider.fetch_activity_summary("2026-04-10T00:00:00+08:00", "2026-04-10T23:59:59+08:00"),
            {"apps": [{"name": "Cursor", "minutes": 12}]},
        )


if __name__ == "__main__":
    unittest.main()
