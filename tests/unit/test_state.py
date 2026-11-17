"""Synthetic disposable SQLite tests only; user DBs must never be opened."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from my_local_ai.state.migrations import APP_ID, REQUIRED_TABLES, SCHEMA_VERSION
from my_local_ai.state.sqlite_store import initialize_state

class SQLiteStateTests(unittest.TestCase):
    def test_bootstrap_wal_fk_and_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            receipt = initialize_state(path)
            self.assertEqual(receipt.schema_version, SCHEMA_VERSION)
            self.assertIsNone(receipt.backup_name)
            self.assertEqual(len(receipt.ddl_sha256), 64)
            with sqlite3.connect(path) as db:
                tables = {x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue(REQUIRED_TABLES.issubset(tables))
                self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
                self.assertEqual(db.execute("PRAGMA application_id").fetchone()[0], APP_ID)
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_reopen_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            initialize_state(path)
            second = initialize_state(path)
            self.assertIsNone(second.backup_name)

    def test_owned_v0_requires_backup_before_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute(f"PRAGMA application_id={APP_ID}")
                db.execute("PRAGMA user_version=0")
            receipt = initialize_state(path)
            self.assertIsNotNone(receipt.backup_name)
            snapshot = path.with_name(receipt.backup_name)
            self.assertTrue(snapshot.exists())
            with sqlite3.connect(snapshot) as old:
                self.assertEqual(old.execute("PRAGMA user_version").fetchone()[0], 0)
            with sqlite3.connect(path) as newer:
                self.assertEqual(newer.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_unknown_customer_db_rejected_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "customer.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE private_data(value TEXT)")
                db.execute("INSERT INTO private_data VALUES('keep')")
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                initialize_state(path)
            self.assertEqual(path.read_bytes(), original)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "real.sqlite3"
            initialize_state(target)
            link = Path(temp) / "alias.sqlite3"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValueError):
                initialize_state(link)

    def test_unowned_v0_tables_refused_without_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute(f"PRAGMA application_id={APP_ID}")
                db.execute("CREATE TABLE unknown_legacy(payload TEXT)")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                initialize_state(path)
            self.assertEqual(path.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
