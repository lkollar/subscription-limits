import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("serve_guard", Path(__file__).parents[1] / "nix/serve-guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
HOST = "example.ts.net:8443"


class ServeGuardTests(unittest.TestCase):
    def test_rejects_both_conflicting_mount_variants(self):
        for path in ("/limits", "/limits/"):
            before = {"Web": {HOST: {"Handlers": {path: {"Text": "existing"}}}}}
            saved = copy.deepcopy(before)
            with self.assertRaises(ValueError):
                guard.check(before, HOST)
            self.assertEqual(before, saved)

    def test_rejects_slash_variant_even_if_proxy_matches(self):
        before = {"Web": {HOST: {"Handlers": {"/limits/": {"Proxy": "http://127.0.0.1:18740"}}}}}
        with self.assertRaises(ValueError):
            guard.check(before, HOST)

    def test_rejects_http_or_tcp_port(self):
        for tcp in ({"HTTP": True}, {"TCPForward": "127.0.0.1:1234"}, {"HTTPS": False}):
            with self.assertRaises(ValueError):
                guard.check({"TCP": {"8443": tcp}}, HOST)

    def test_rejects_funnel(self):
        with self.assertRaises(ValueError):
            guard.check({"AllowFunnel": {HOST: True}}, HOST)

    def test_accepts_additive_private_route_and_preserves_existing(self):
        before = {"TCP": {"8443": {"HTTPS": True}}, "Web": {HOST: {"Handlers": {"/other": {"Proxy": "http://127.0.0.1:1234"}}}}}
        after = copy.deepcopy(before)
        after["Web"][HOST]["Handlers"]["/limits"] = {"Proxy": "http://127.0.0.1:18740"}
        guard.check(before, HOST)
        guard.check(before, HOST, after)
        guard.check(after, HOST)

    def test_detects_changed_existing_route(self):
        before = {"Web": {HOST: {"Handlers": {"/other": {"Text": "preserve"}}}}}
        after = {"Web": {HOST: {"Handlers": {"/limits": {"Proxy": "http://127.0.0.1:18740"}}}}}
        with self.assertRaises(ValueError):
            guard.check(before, HOST, after)
