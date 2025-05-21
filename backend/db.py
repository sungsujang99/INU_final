# db.py
import sqlite3

DB_NAME = "database.db"


def init_db():
    """앱 기동 때 호출: 테이블이 없으면 생성"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # ① 입·출 이력
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code   TEXT NOT NULL,
            product_name   TEXT NOT NULL,
            rack           TEXT NOT NULL,        -- 'A'/'B'/'C'
            slot           INTEGER NOT NULL,     -- 1-80
            movement_type  TEXT NOT NULL,        -- 'IN' / 'OUT'
            quantity       INTEGER NOT NULL,
            cargo_owner    TEXT,
            timestamp      TEXT NOT NULL,
            batch_id       TEXT
        );
    """)

    # ② 현재 재고
    cur.execute("""
        CREATE TABLE IF NOT EXISTS current_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code    TEXT NOT NULL,
            product_name    TEXT NOT NULL,
            rack            TEXT NOT NULL,
            slot            INTEGER NOT NULL,
            total_quantity  INTEGER NOT NULL,
            cargo_owner     TEXT,
            last_update     TEXT NOT NULL
        );
    """)

    # ③ 사용자 정보
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT
        );
    """)

    # ④ 작업 작업
    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rack TEXT NOT NULL,
            slot INTEGER NOT NULL,
            product_code TEXT NOT NULL,
            product_name TEXT NOT NULL,
            movement TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            cargo_owner TEXT,
            status TEXT NOT NULL, -- 'pending', 'in_progress', 'done'
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()
