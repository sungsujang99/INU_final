# db.py
import sqlite3

DB_NAME = "database.db"


def init_db():
    """앱 기동 때 호출: 테이블이 없으면 생성"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # ① 입·출 이력 (User actions are tracked here)
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
            batch_id       TEXT,
            user_id        INTEGER,             -- ID of the user who performed the action
            username       TEXT NOT NULL,        -- Username for quick reference
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)

    # ② 현재 재고 (Physical equipment state - independent of users)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS current_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code    TEXT NOT NULL,
            product_name    TEXT NOT NULL,
            rack            TEXT NOT NULL,
            slot            INTEGER NOT NULL,
            total_quantity  INTEGER NOT NULL,
            cargo_owner     TEXT,
            last_update     TEXT NOT NULL        -- Just timestamp, no user tracking
        );
    """)

    # ③ 사용자 정보
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,       -- User's login ID
            display_name TEXT NOT NULL,          -- User's display name
            hashed_password TEXT NOT NULL,
            role TEXT
        );
    """)

    # ④ 작업 작업 (User actions are tracked here)
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
            updated_at TEXT NOT NULL,
            start_time TEXT,      -- Added for task timing
            end_time TEXT,        -- Added for task timing
            created_by INTEGER,   -- ID of the user who created the task
            FOREIGN KEY (created_by) REFERENCES users (id)
        );
    """)

    # ⑤ Batch Task Links (User actions are tracked here)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS batch_task_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            created_by INTEGER,   -- ID of the user who created the batch
            FOREIGN KEY (task_id) REFERENCES work_tasks (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_batch_task_links_batch_id ON batch_task_links (batch_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_batch_task_links_task_id ON batch_task_links (task_id);")

    conn.commit()
    conn.close()
