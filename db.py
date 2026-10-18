import sqlite3
from pathlib import Path
from flask import g

MAX_SQLITE_INTEGER = 2**63 - 1


def get_connection():
    con = sqlite3.connect("database.db")
    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    return con


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def initialize_schema():
    con = get_connection()
    init_sql = Path(__file__).with_name("init.sql").read_text(encoding="utf-8")
    con.executescript(init_sql)
    con.close()


def execute(sql, params=[]):
    con = get_connection()
    result = con.execute(sql, params)
    con.commit()
    g.last_insert_id = result.lastrowid
    con.close()


def last_insert_id():
    return g.last_insert_id


def query(sql, params=[]):
    con = get_connection()
    result = con.execute(sql, params).fetchall()
    con.close()
    return result
