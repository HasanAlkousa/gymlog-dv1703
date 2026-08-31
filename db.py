"""
Database access layer.

Deliberately thin: it opens connections and hands back rows as dicts.
No ORM is used anywhere in this project - every statement is written by
hand in queries.py and passed through here with parameter binding.
"""
import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

DB_CONFIG = {
    "host": os.getenv("GYMLOG_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("GYMLOG_DB_PORT", "3306")),
    "user": os.getenv("GYMLOG_DB_USER", "root"),
    "password": os.getenv("GYMLOG_DB_PASSWORD", ""),
    "database": os.getenv("GYMLOG_DB_NAME", "gymlog"),
    "charset": "utf8mb4",
    "autocommit": False,
}

_pool = pooling.MySQLConnectionPool(pool_name="gymlog_pool", pool_size=5, **DB_CONFIG)


@contextmanager
def get_cursor(dictionary=True, commit=False):
    """Yield a cursor and make sure the connection is always returned."""
    conn = _pool.get_connection()
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def query_all(sql, params=()):
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=()):
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=()):
    """Run INSERT/UPDATE/DELETE. Returns the new id when there is one."""
    with get_cursor(commit=True) as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def call_proc(name, args):
    """Call a stored procedure. Returns the argument tuple with OUT
    parameters filled in (a plain cursor is used here on purpose: a
    dictionary cursor would hand the OUT parameters back as a dict)."""
    with get_cursor(dictionary=False, commit=True) as cur:
        result = cur.callproc(name, args)
        # Drain any result sets the procedure produced.
        for _ in cur.stored_results():
            pass
        return result
