import os
import tempfile
from pathlib import Path
from unittest.mock import patch

def test_db_creates_on_first_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        ridge_dir = Path(tmpdir) / ".ridge"
        with patch("ridge.storage.RIDGE_DIR", ridge_dir):
            with patch("ridge.storage.DB_PATH", ridge_dir / "data.db"):
                from ridge.storage import get_db
                conn = get_db()
                assert (ridge_dir / "data.db").exists()
                conn.close()