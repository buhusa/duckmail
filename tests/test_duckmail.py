import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import duckmail


class DuckMailTests(unittest.TestCase):
    def test_default_config_is_stored_in_project_directory(self):
        project_dir = Path(duckmail.__file__).resolve().parent

        self.assertEqual(
            duckmail.DEFAULT_CONFIG,
            project_dir / ".duckmail" / "config.json",
        )

    def test_config_roundtrip_remembers_token_and_last_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            config = duckmail.Config(path)

            config.save({"token": "secret", "last_address": "alpha@duck.com"})

            self.assertEqual(
                config.load(),
                {"token": "secret", "last_address": "alpha@duck.com"},
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_client_returns_full_duck_address(self):
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps({"address": "amaze-gem-spider"}).encode()

        opener = Mock(return_value=response)
        client = duckmail.DuckMailClient("token", opener=opener)

        self.assertEqual(client.create_address(), "amaze-gem-spider@duck.com")
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, duckmail.API_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer token")

    def test_cli_show_prints_last_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save({"token": "secret", "last_address": "alpha@duck.com"})
            out = io.StringIO()

            code = duckmail.main(["show", "--config", str(config.path)], stdout=out)

            self.assertEqual(code, 0)
            self.assertIn("alpha@duck.com", out.getvalue())

    def test_cli_new_saves_generated_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save({"token": "secret"})
            out = io.StringIO()
            client_factory = Mock(
                return_value=Mock(create_address=Mock(return_value="beta@duck.com"))
            )

            code = duckmail.main(
                ["new", "--config", str(config.path)],
                stdout=out,
                client_factory=client_factory,
            )

            self.assertEqual(code, 0)
            self.assertIn("beta@duck.com", out.getvalue())
            self.assertEqual(config.load()["last_address"], "beta@duck.com")

    def test_cli_new_saves_labelled_address_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save({"token": "secret"})
            out = io.StringIO()
            client_factory = Mock(
                return_value=Mock(create_address=Mock(return_value="gamma@duck.com"))
            )

            code = duckmail.main(
                ["new", "--label", "github", "--config", str(config.path)],
                stdout=out,
                client_factory=client_factory,
            )

            self.assertEqual(code, 0)
            self.assertIn("gamma@duck.com", out.getvalue())
            entry = config.load()["addresses"][0]
            self.assertEqual(entry["address"], "gamma@duck.com")
            self.assertEqual(entry["label"], "github")
            self.assertIn("created_at", entry)

    def test_cli_new_with_label_generates_and_remembers_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save({"token": "secret"})
            out = io.StringIO()
            client_factory = Mock(
                return_value=Mock(create_address=Mock(return_value="labelled@duck.com"))
            )

            code = duckmail.main(
                ["new-with-label", "bank", "--config", str(config.path)],
                stdout=out,
                client_factory=client_factory,
            )

            self.assertEqual(code, 0)
            self.assertIn("labelled@duck.com", out.getvalue())
            entry = config.load()["addresses"][0]
            self.assertEqual(entry["address"], "labelled@duck.com")
            self.assertEqual(entry["label"], "bank")
            self.assertIn("New Duck address", out.getvalue())
            self.assertIn("Label: bank", out.getvalue())

    def test_cli_list_prints_saved_labels_and_addresses(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save(
                {
                    "addresses": [
                        {"label": "github", "address": "gamma@duck.com"},
                        {"label": "newsletter", "address": "delta@duck.com"},
                    ]
                }
            )
            out = io.StringIO()

            code = duckmail.main(["list", "--config", str(config.path)], stdout=out)

            self.assertEqual(code, 0)
            self.assertIn("Saved Duck addresses", out.getvalue())
            self.assertIn("LABEL", out.getvalue())
            self.assertIn("ADDRESS", out.getvalue())
            self.assertIn("CREATED", out.getvalue())
            self.assertIn("github", out.getvalue())
            self.assertIn("gamma@duck.com", out.getvalue())
            self.assertIn("newsletter", out.getvalue())

    def test_cli_list_formats_existing_utc_timestamp_as_local_readable_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save(
                {
                    "addresses": [
                        {
                            "label": "github",
                            "address": "gamma@duck.com",
                            "created_at": "2026-05-01T20:44:08+00:00",
                        },
                    ]
                }
            )
            out = io.StringIO()

            code = duckmail.main(["list", "--config", str(config.path)], stdout=out)

            self.assertEqual(code, 0)
            self.assertIn("2026-05-01 at 22:44", out.getvalue())
            self.assertNotIn("+00:00", out.getvalue())

    def test_cli_find_filters_history_by_label_or_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save(
                {
                    "addresses": [
                        {"label": "github", "address": "gamma@duck.com"},
                        {"label": "newsletter", "address": "delta@duck.com"},
                    ]
                }
            )
            out = io.StringIO()

            code = duckmail.main(
                ["find", "git", "--config", str(config.path)],
                stdout=out,
            )

            self.assertEqual(code, 0)
            self.assertIn("github", out.getvalue())
            self.assertNotIn("newsletter", out.getvalue())

    def test_cli_relabel_updates_existing_address_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save(
                {
                    "addresses": [
                        {"label": "old", "address": "gamma@duck.com"},
                        {"label": "newsletter", "address": "delta@duck.com"},
                    ]
                }
            )
            out = io.StringIO()

            code = duckmail.main(
                ["relabel", "gamma@duck.com", "github", "--config", str(config.path)],
                stdout=out,
            )

            self.assertEqual(code, 0)
            self.assertIn("Updated label", out.getvalue())
            addresses = config.load()["addresses"]
            self.assertEqual(addresses[0]["label"], "github")
            self.assertEqual(addresses[0]["address"], "gamma@duck.com")
            self.assertEqual(addresses[1]["label"], "newsletter")

    def test_cli_relabel_can_match_current_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = duckmail.Config(Path(tmp) / "config.json")
            config.save(
                {"addresses": [{"label": "old", "address": "gamma@duck.com"}]}
            )
            out = io.StringIO()

            code = duckmail.main(
                ["relabel", "old", "github", "--config", str(config.path)],
                stdout=out,
            )

            self.assertEqual(code, 0)
            self.assertEqual(config.load()["addresses"][0]["label"], "github")

    def test_interactive_screen_clears_terminal_and_renders_latest_result(self):
        out = io.StringIO()

        duckmail.render_interactive_screen(
            {"last_address": "alpha@duck.com"},
            out,
            message="New Duck address\n----------------\nAddress: alpha@duck.com",
        )

        rendered = out.getvalue()
        self.assertTrue(rendered.startswith(duckmail.CLEAR_SCREEN))
        self.assertIn("duckmail", rendered)
        self.assertIn("Current: alpha@duck.com", rendered)
        self.assertIn("Last result", rendered)
        self.assertIn("Address: alpha@duck.com", rendered)
        self.assertIn("2. New address with label", rendered)
        self.assertIn("5. Change label", rendered)


if __name__ == "__main__":
    unittest.main()
