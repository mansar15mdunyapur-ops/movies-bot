# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime

DB_NAME = 'movies.db'

def init_database():
    """Initialize database with all tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Movies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id INTEGER UNIQUE,
            title TEXT NOT NULL,
            year INTEGER,
            quality TEXT,
            file_id TEXT,
            file_size TEXT,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by INTEGER
        )
    ''')
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_requests INTEGER DEFAULT 0,
            user_type TEXT DEFAULT 'paid',
            payment_status TEXT DEFAULT 'inactive',
            expiry_date TIMESTAMP,
            license_key TEXT UNIQUE
        )
    ''')
    
    # Licenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            user_id INTEGER,
            plan TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_date TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Pending payments table (SECURE PAYMENT SYSTEM)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT UNIQUE,
            user_id INTEGER,
            amount REAL,
            plan TEXT,
            transaction_id TEXT,
            screenshot_file_id TEXT,
            status TEXT DEFAULT 'pending',
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified_at TIMESTAMP
        )
    ''')
    
    # Upgrade requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS upgrade_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            old_plan TEXT,
            new_plan TEXT,
            payment_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_title TEXT,
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# ========== USER FUNCTIONS ==========
def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_total_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ========== MOVIE FUNCTIONS ==========
def get_total_movies():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM movies')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def search_movies_db(query):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT tmdb_id, title, year FROM movies 
        WHERE title LIKE ? ORDER BY year DESC
    ''', (f'%{query}%',))
    results = cursor.fetchall()
    conn.close()
    return results

# ========== REQUEST FUNCTIONS ==========
def add_request(user_id, movie_title):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO requests (user_id, movie_title)
        VALUES (?, ?)
    ''', (user_id, movie_title))
    conn.commit()
    conn.close()

def get_pending_requests():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM requests WHERE status = "pending" ORDER BY request_date DESC')
    requests = cursor.fetchall()
    conn.close()
    return requests

def get_total_requests():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM requests WHERE status = "pending"')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ========== PAYMENT FUNCTIONS ==========
def save_pending_payment(payment_id, user_id, amount, plan, transaction_id=None, screenshot_id=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pending_payments (payment_id, user_id, amount, plan, transaction_id, screenshot_file_id, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    ''', (payment_id, user_id, amount, plan, transaction_id, screenshot_id))
    conn.commit()
    conn.close()

def update_payment_with_screenshot(payment_id, screenshot_file_id, transaction_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pending_payments 
        SET screenshot_file_id = ?, transaction_id = ?
        WHERE payment_id = ? AND status = 'pending'
    ''', (screenshot_file_id, transaction_id, payment_id))
    conn.commit()
    conn.close()

def get_pending_payment(payment_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, plan FROM pending_payments WHERE payment_id = ? AND status = "pending"', (payment_id,))
    payment = cursor.fetchone()
    conn.close()
    return payment

def get_all_pending_payments():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT payment_id, user_id, amount, plan, created_at 
        FROM pending_payments WHERE status = "pending" 
        ORDER BY created_at DESC
    ''')
    payments = cursor.fetchall()
    conn.close()
    return payments

def approve_payment(payment_id, admin_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pending_payments 
        SET status = 'approved', verified_at = CURRENT_TIMESTAMP, admin_notes = ?
        WHERE payment_id = ?
    ''', (f"Approved by admin {admin_id}", payment_id))
    conn.commit()
    conn.close()

def reject_payment(payment_id, admin_id, reason):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pending_payments 
        SET status = 'rejected', admin_notes = ?
        WHERE payment_id = ?
    ''', (f"Rejected by admin {admin_id}: {reason}", payment_id))
    conn.commit()
    conn.close()

def save_license(license_key, user_id, plan, days):
    from datetime import datetime, timedelta
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    expiry_date = datetime.now() + timedelta(days=days)
    
    cursor.execute('''
        INSERT INTO licenses (license_key, user_id, plan, expiry_date, status)
        VALUES (?, ?, ?, ?, 'active')
    ''', (license_key, user_id, plan, expiry_date))
    
    cursor.execute('''
        UPDATE users 
        SET user_type = 'paid', payment_status = 'active', expiry_date = ?, license_key = ?
        WHERE user_id = ?
    ''', (expiry_date, license_key, user_id))
    
    conn.commit()
    conn.close()
    return license_key

def get_user_license(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT plan, expiry_date, license_key 
        FROM licenses 
        WHERE user_id = ? AND status = 'active'
    ''', (user_id,))
    license = cursor.fetchone()
    conn.close()
    return license

def extend_license(user_id, additional_days):
    from datetime import datetime, timedelta
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT expiry_date FROM licenses WHERE user_id = ? AND status = "active"', (user_id,))
    current = cursor.fetchone()
    
    if current:
        current_expiry = datetime.strptime(current[0], '%Y-%m-%d %H:%M:%S.%f')
        new_expiry = current_expiry + timedelta(days=additional_days)
        
        cursor.execute('''
            UPDATE licenses SET expiry_date = ? WHERE user_id = ? AND status = 'active'
        ''', (new_expiry, user_id))
        
        cursor.execute('''
            UPDATE users SET expiry_date = ? WHERE user_id = ?
        ''', (new_expiry, user_id))
        
        conn.commit()
        conn.close()
        return new_expiry
    
    conn.close()
    return None

# ========== UPGRADE FUNCTIONS ==========
def save_upgrade_request(user_id, old_plan, new_plan, payment_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO upgrade_requests (user_id, old_plan, new_plan, payment_id, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (user_id, old_plan, new_plan, payment_id))
    conn.commit()
    conn.close()

def get_active_license_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
    count = cursor.fetchone()[0]
    conn.close()
    return count

if __name__ == '__main__':
    init_database()
