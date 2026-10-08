import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "samples"))
from network_probe import check_marker, is_lab_private, private_dns, storage_text


class PrivateEvidenceTests(unittest.TestCase):
    def test_accepts_rfc1918(self):
        for address in ("10.42.1.10", "172.16.2.3", "192.168.1.2"):
            self.assertTrue(is_lab_private(address))

    def test_accepts_documented_cgnat_space(self):
        self.assertTrue(is_lab_private("100.64.1.1"))

    def test_rejects_public_loopback_linklocal_and_documentation(self):
        for address in ("8.8.8.8", "127.0.0.1", "169.254.1.1", "192.0.2.1", "::1"):
            self.assertFalse(is_lab_private(address))

    def test_rejects_invalid_ip(self):
        with self.assertRaises(ValueError):
            is_lab_private("not-an-ip")

    def test_marker_matches_ignoring_line_ending(self):
        self.assertEqual(check_marker("nonce-42\n", "nonce-42"), "nonce-42")

    def test_old_marker_is_failure(self):
        with self.assertRaises(RuntimeError):
            check_marker("old", "new")

    def test_blank_expected_marker_is_failure(self):
        with self.assertRaises(ValueError):
            check_marker("", " ")

    @patch("network_probe.socket.getaddrinfo")
    def test_dns_rejects_mixed_public_private(self, resolver):
        resolver.return_value = [
            (2, 1, 6, "", ("10.42.1.7", 443)),
            (2, 1, 6, "", ("20.1.1.1", 443)),
        ]
        with self.assertRaises(RuntimeError):
            private_dns("example", 443)

    @patch("network_probe.socket.getaddrinfo")
    def test_dns_returns_unique_private_ips(self, resolver):
        resolver.return_value = [
            (2, 1, 6, "", ("10.42.1.7", 443)),
            (2, 1, 6, "", ("10.42.1.7", 443)),
        ]
        self.assertEqual(private_dns("example", 443), ["10.42.1.7"])

    @patch("network_probe.socket.getaddrinfo", return_value=[])
    def test_empty_dns_is_failure(self, resolver):
        with self.assertRaises(RuntimeError):
            private_dns("example", 443)


class StorageRequestTests(unittest.TestCase):
    def setUp(self):
        self.credential = MagicMock()
        self.credential.get_token.return_value = SimpleNamespace(token="local-test-token")

    @patch("network_probe.build_opener")
    def test_blob_uses_oauth_date_and_version(self, build):
        opener = build.return_value
        opener.open.return_value.__enter__.return_value.read.return_value = b"marker\n"
        self.assertEqual(
            storage_text("https://account.blob.core.windows.net/labdata/marker.txt",
                         self.credential),
            "marker\n",
        )
        request = opener.open.call_args.args[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["authorization"], "Bearer local-test-token")
        self.assertIn("GMT", headers["x-ms-date"])
        self.assertEqual(headers["x-ms-version"], "2023-11-03")
        self.assertNotIn("x-ms-file-request-intent", headers)
        self.credential.get_token.assert_called_once_with(
            "https://storage.azure.com/.default"
        )

    @patch("network_probe.build_opener")
    def test_files_explicitly_sets_backup_intent(self, build):
        build.return_value.open.return_value.__enter__.return_value.read.return_value = b"x"
        storage_text("https://account.file.core.windows.net/labfiles/marker.txt",
                     self.credential, files=True)
        request = build.return_value.open.call_args.args[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["x-ms-file-request-intent"], "backup")

    @patch("network_probe.build_opener")
    def test_request_failure_propagates(self, build):
        build.return_value.open.side_effect = RuntimeError("simulated request failure")
        with self.assertRaisesRegex(RuntimeError, "simulated request failure"):
            storage_text("https://account.blob.core.windows.net/labdata/marker.txt",
                         self.credential)


if __name__ == "__main__":
    unittest.main()
