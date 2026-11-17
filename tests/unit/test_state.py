"""Synthetic disposable SQLite tests only; user DBs must never be opened."""
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import unittest

from my_local_ai.state.migrations import APP_ID, REQUIRED_TABLES, SCHEMA_VERSION, canonical_schema_sql
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
            self.assertEqual(receipt.backup_sha256, hashlib.sha256(snapshot.read_bytes()).hexdigest())
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


    def test_canonical_schema_mapping_matches_required_tables(self):
        self.assertEqual(set(canonical_schema_sql()), REQUIRED_TABLES)

    def test_v1_schema_drift_rejected_without_overwriting_data(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            initialize_state(path)
            db = sqlite3.connect(path)
            try:
                db.execute("INSERT INTO plans(plan_id,plan_sha,blueprint_sha) VALUES ('keep','p','b')")
                db.execute("ALTER TABLE plans ADD COLUMN injected TEXT")
                db.commit()
            finally:
                db.close()
            with self.assertRaisesRegex(ValueError, "schema drift"):
                initialize_state(path)
            with sqlite3.connect(path) as verify:
                self.assertEqual(verify.execute("SELECT plan_id FROM plans").fetchone()[0], "keep")

    def test_owned_v1_foreign_key_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            initialize_state(path)
            db = sqlite3.connect(path)
            try:
                db.execute("PRAGMA foreign_keys=OFF")
                db.execute("INSERT INTO tasks(plan_id,task_id,source_sha) VALUES ('missing','t1','abc')")
                db.commit()
            finally:
                db.close()
            with self.assertRaisesRegex(ValueError, "foreign keys"):
                initialize_state(path)

    def test_triggers_are_not_allowed_in_owned_state(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            initialize_state(path)
            db = sqlite3.connect(path)
            try:
                db.execute("CREATE TRIGGER sneaky AFTER INSERT ON plans BEGIN SELECT 1; END")
                db.commit()
            finally:
                db.close()
            with self.assertRaises(ValueError):
                initialize_state(path)

    def test_sidecar_symlink_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            target = Path(temp) / "unrelated.txt"
            target.write_text("retain", encoding="utf-8")
            link = Path(temp) / "synthetic.sqlite3-wal"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValueError):
                initialize_state(path)
            self.assertEqual(target.read_text(encoding="utf-8"), "retain")
            self.assertFalse(path.exists())

    def test_unexpected_existing_state_version_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.sqlite3"
            db = sqlite3.connect(path)
            try:
                db.execute(f"PRAGMA application_id={APP_ID}")
                db.execute("PRAGMA user_version=500")
            finally:
                db.close()
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                initialize_state(path)
            self.assertEqual(path.read_bytes(), original)

if __name__ == "__main__":
    unittest.main()



class SqliteLexicalPathAndIdentityTests(unittest.TestCase):
    def test_reject_parent_traversal_even_if_it_normalizes_to_same_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"local.sqlite3"
            initialize_state(path)
            before=path.read_bytes()
            with self.assertRaises(ValueError):
                initialize_state(root/"sub"/".."/"local.sqlite3")
            self.assertEqual(path.read_bytes(),before)

    def test_state_header_read_uses_nofollow_and_consistent_inode(self):
        import my_local_ai.state.sqlite_store as store
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"local.sqlite3"
            initialize_state(path)
            original_open=store.os.open
            def swapped_open(target,flags,*args,**kwargs):
                if Path(target)==path:
                    path.rename(path.with_suffix(".old"))
                    path.write_bytes(b"not-an-owner-database")
                return original_open(target,flags,*args,**kwargs)
            with patch.object(store.os,"open",side_effect=swapped_open):
                with self.assertRaises(ValueError):
                    store._inspect_existing(path)
