import unittest

import worker


class OpeningIdentityTests(unittest.TestCase):
    def test_exact_immutable_identity_is_accepted(self):
        worker.verify_run_book_identity(
            {
                "book": "xfish-uho.epd",
                "book_sha256": "a" * 64,
                "book_positions": 100000,
                "opening_seed": "stc-seed",
            },
            "xfish-uho.epd",
            "a" * 64,
            100000,
            "stc-seed",
        )

    def test_old_or_mismatched_book_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "book ID"):
            worker.verify_run_book_identity(
                {
                    "book": "xiangqi.epd",
                    "book_sha256": "a" * 64,
                    "book_positions": 33921,
                    "opening_seed": "old-seed",
                },
                "xfish-uho.epd",
                "b" * 64,
                100000,
                "new-seed",
            )

    def test_missing_server_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "immutable opening metadata"):
            worker.verify_run_book_identity(
                {"book": "xfish-uho.epd"},
                "xfish-uho.epd",
                "a" * 64,
                100000,
                "stc-seed",
            )


if __name__ == "__main__":
    unittest.main()
