import sqlite3
from pathlib import Path


DB_PATH = Path("smartphoto.db")


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT NOT NULL,
            scene TEXT,
            iso TEXT,
            aperture TEXT,
            shutter TEXT,
            retention_mode TEXT DEFAULT '24h',
            saved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )

    # 檢查 photos 表目前有哪些欄位
    columns = connection.execute(
        "PRAGMA table_info(photos)"
    ).fetchall()

    column_names = {
        row[1]
        for row in columns
    }

    # 舊資料庫沒有 simulated_filename 時，自動補上
    if "simulated_filename" not in column_names:
        connection.execute(
            """
            ALTER TABLE photos
            ADD COLUMN simulated_filename TEXT
            """
        )

    connection.commit()
    connection.close()