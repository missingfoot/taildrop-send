import os
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import core

TARGETS = (
    "100.87.151.104\tipad-pro-11-gen-1\n"
    "100.79.126.117\tmi\toffline; last seen 44m0s ago\n"
    "100.74.135.24\tiphone\n"
    "100.119.203.25\tnas\toffline; last seen 831h11m0s ago\n"
)


class ParseTargetsTests(unittest.TestCase):
    def test_online_first_then_offline_keeping_order(self):
        names = [d["name"] for d in core.parse_targets(TARGETS)]
        self.assertEqual(names, ["ipad-pro-11-gen-1", "iphone", "mi", "nas"])

    def test_fields(self):
        devices = {d["name"]: d for d in core.parse_targets(TARGETS)}
        self.assertEqual(
            devices["iphone"], {"name": "iphone", "ip": "100.74.135.24", "online": True, "note": ""}
        )
        self.assertEqual(devices["mi"]["online"], False)
        self.assertEqual(devices["mi"]["note"], "offline 44m")
        self.assertEqual(devices["nas"]["note"], "offline 34d")

    def test_blank_and_junk_lines_ignored(self):
        self.assertEqual(core.parse_targets("\n  \nnot-a-target\n"), [])

    def test_offline_without_last_seen(self):
        (dev,) = core.parse_targets("1.2.3.4\tbox\toffline\n")
        self.assertEqual((dev["online"], dev["note"]), (False, "offline"))


class ShortDurationTests(unittest.TestCase):
    def test_examples(self):
        cases = {
            "12s": "now",
            "44m0s": "44m",
            "5h3m0s": "5h",
            "47h59m0s": "47h",
            "48h0m0s": "2d",
            "831h11m0s": "34d",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(core.short_duration(text), expected)

    def test_unparseable_returned_unchanged(self):
        self.assertEqual(core.short_duration("a while"), "a while")


class ExpandPathsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.out = self.tmp / "out"
        self.out.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_files_pass_through(self):
        f = self.tmp / "a.jpg"
        f.write_text("x")
        self.assertEqual(core.expand_paths([str(f)], str(self.out)), [str(f)])
        self.assertEqual(list(self.out.iterdir()), [])

    def test_folder_is_zipped_with_its_name_as_top_level(self):
        folder = self.tmp / "Holiday"
        (folder / "sub").mkdir(parents=True)
        (folder / "a.txt").write_text("a")
        (folder / "sub" / "b.txt").write_text("b")
        (result,) = core.expand_paths([str(folder)], str(self.out))
        self.assertEqual(result, str(self.out / "Holiday.zip"))
        with zipfile.ZipFile(result) as zf:
            names = set(zf.namelist())
        self.assertIn("Holiday/a.txt", names)
        self.assertIn("Holiday/sub/b.txt", names)

    def test_same_named_folders_get_distinct_zips(self):
        for parent in ("x", "y"):
            d = self.tmp / parent / "Photos"
            d.mkdir(parents=True)
            (d / "p.txt").write_text(parent)
        results = core.expand_paths(
            [str(self.tmp / "x" / "Photos"), str(self.tmp / "y" / "Photos")], str(self.out)
        )
        self.assertEqual([os.path.basename(r) for r in results], ["Photos.zip", "Photos-2.zip"])

    def test_trailing_slash_on_folder(self):
        folder = self.tmp / "Docs"
        folder.mkdir()
        (folder / "d.txt").write_text("d")
        (result,) = core.expand_paths([str(folder) + "/"], str(self.out))
        self.assertEqual(os.path.basename(result), "Docs.zip")


class SendCommandTests(unittest.TestCase):
    def test_builds_cp_with_trailing_colon(self):
        self.assertEqual(
            core.send_command("/usr/bin/tailscale", ["/a b.jpg", "/c.pdf"], "iphone"),
            ["/usr/bin/tailscale", "file", "cp", "/a b.jpg", "/c.pdf", "iphone:"],
        )

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            core.send_command("tailscale", [], "iphone")


class ExplainErrorTests(unittest.TestCase):
    def test_access_denied_suggests_operator(self):
        msg = core.explain_error("Access denied: cp access denied")
        self.assertIn("sudo tailscale set --operator=$USER", msg)

    def test_daemon_not_running(self):
        msg = core.explain_error(
            "failed to connect to local tailscaled; it doesn't appear to be running"
        )
        self.assertIn("isn't running", msg)

    def test_logged_out(self):
        self.assertIn("logged in", core.explain_error("Logged out.\nLog in at: https://x"))

    def test_unknown_error_passed_through(self):
        self.assertEqual(core.explain_error("  boom \n"), "boom")


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "sub" / "config.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_or_corrupt_gives_defaults(self):
        self.assertEqual(core.load_config(self.path), {"last_device": None})
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{nope")
        self.assertEqual(core.load_config(self.path), {"last_device": None})

    def test_roundtrip_creates_parent_and_no_temp_left(self):
        core.save_config(self.path, {"last_device": "iphone"})
        self.assertEqual(core.load_config(self.path), {"last_device": "iphone"})
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["config.json"])

    def test_non_string_last_device_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"last_device": 5}')
        self.assertEqual(core.load_config(self.path), {"last_device": None})


class ArgToPathTests(unittest.TestCase):
    def test_plain_and_url(self):
        self.assertEqual(core.arg_to_path("/x/a b"), "/x/a b")
        self.assertEqual(core.arg_to_path("file:///x/a%20b"), "/x/a b")


if __name__ == "__main__":
    unittest.main()
