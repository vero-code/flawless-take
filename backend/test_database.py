"""
test_database.py - Unit & Integration tests for SQLite Database Repository
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import database


async def test_database_crud():
    print("[1/3] Initializing Isolated Test Database...")
    temp_dir = tempfile.TemporaryDirectory()
    orig_db_path = database.DB_PATH
    test_db_path = Path(temp_dir.name) / "test_flawless.db"
    database.DB_PATH = test_db_path

    try:
        await database.init_db()
        assert test_db_path.exists(), "Test database file was not created"
        print("  OK: Database schema created successfully.")

        print("[2/3] Testing save_check and save_comparison...")
        check_id = await database.save_check(
            scene="Scene 99",
            character="Hero",
            take="1",
            risk_level="LOW",
            script_grounded=True,
            report="Clean baseline take report",
            preview_ref="take1.jpg",
        )
        assert check_id is not None and check_id > 0

        comp_id = await database.save_comparison(
            scene="Scene 99",
            character="Hero",
            take_ref="1",
            take_current="2",
            risk_level="MEDIUM",
            match_score="FAIR",
            script_grounded=True,
            report="Tie slightly loose in take 2",
            preview_ref="take1.jpg",
            preview_cur="take2.jpg",
        )
        assert comp_id is not None and comp_id > check_id
        print("  OK: Records inserted successfully.")

        print("[3/3] Testing list_records, get_record, and get_scene_chronology...")
        records = await database.list_records(scene="Scene 99")
        assert len(records) == 2

        single = await database.get_record(check_id)
        assert single is not None
        assert single["scene"] == "Scene 99"
        assert single["character"] == "Hero"

        chronology = await database.get_scene_chronology("Scene 99", "Hero")
        assert len(chronology) == 2
        assert chronology[0]["take"] == "1"
        assert chronology[1]["take_current"] == "2"
        print("  OK: Record retrieval and scene chronology verified.")

    finally:
        database.DB_PATH = orig_db_path
        temp_dir.cleanup()


if __name__ == "__main__":
    print("=== Flawless Take Database Repository Tests ===\n")
    try:
        asyncio.run(test_database_crud())
        print("\n=== ALL DATABASE TESTS PASSED ===")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(1)
