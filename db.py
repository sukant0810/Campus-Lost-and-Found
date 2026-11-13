import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "08102006"),
        database=os.getenv("DB_NAME", "campus_lost_found"),
    )


def run(sql, params=(), one=False, write=False):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        if write:
            conn.commit()
            return cur.rowcount
        return cur.fetchone() if one else cur.fetchall()
    finally:
        cur.close()
        conn.close()


def run_insert(sql, params=()):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


def init_users_table():
    run(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INT AUTO_INCREMENT PRIMARY KEY, "
        "username VARCHAR(50) NOT NULL UNIQUE, "
        "password_hash VARCHAR(255) NOT NULL)",
        write=True,
    )


def init_claim_tables():
    run(
        "CREATE TABLE IF NOT EXISTS verifications ("
        "item_id INT PRIMARY KEY, "
        "question VARCHAR(150) NOT NULL, "
        "answer VARCHAR(100) NOT NULL)",
        write=True,
    )
    run(
        "CREATE TABLE IF NOT EXISTS claims ("
        "id INT AUTO_INCREMENT PRIMARY KEY, "
        "item_id INT NOT NULL, "
        "username VARCHAR(50) NOT NULL, "
        "claimant_name VARCHAR(100) NOT NULL, "
        "contact VARCHAR(100) NOT NULL, "
        "answer VARCHAR(200) NOT NULL, "
        "status VARCHAR(10) NOT NULL DEFAULT 'Pending', "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        write=True,
    )