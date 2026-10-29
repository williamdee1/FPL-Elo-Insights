import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import free_access  # noqa: E402


class FreeAccessTest(unittest.TestCase):
    def test_hash_matches_app_vector(self):
        # Same vector as SquadAI-native/__tests__/paywall.test.ts
        self.assertEqual(free_access.email_hash(" Test@Example.com "),
                         "ba45123746bbe69314444b177f803cec986fbf51aed0bb05e795c0be6e8000bb")

    def test_save_dedupes_sorts_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access" / "free_access.json"
            free_access.save(["b" * 64, "a" * 64, "b" * 64], path)
            self.assertEqual(free_access.load(path), ["a" * 64, "b" * 64])
            self.assertTrue(path.read_bytes().endswith(b"}\n"))
            self.assertEqual(free_access.load(Path(tmp) / "missing.json"), [])

    def test_published_list_is_well_formed(self):
        for digest in free_access.load():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
