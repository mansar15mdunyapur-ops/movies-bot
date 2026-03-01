# -*- coding: utf-8 -*-
import sqlite3
import json
from datetime import datetime

# Database file name
DB_NAME = 'movies.db'

def init_database():
    """Initialize database with all tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Movies table - for storing movie files
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id INTEGER UNIQUE,
            title TEXT NOT NULL,
            year INTEGER,
            quality TEXT,
            file_id TEXT,
            file_size TEXT,
            download_link TEXT,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by INTEGER
        )
    ''')
    
    # Multiple qualities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movie_qualities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id INTEGER,
            quality TEXT,
            file_id TEXT,
            file_size TEXT,
            FOREIGN KEY (tmdb_id) REFERENCES movies(tmdb_id)
        )
    ''')
    
    # Users table (updated with payment fields)
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
    
    # License keys table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            user_id INTEGER,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_date TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Payment history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            payment_method TEXT,
            transaction_id TEXT UNIQUE,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'completed'
        )
    ''')
    
    # Requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tmdb_id INTEGER,
            movie_title TEXT,
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Admin settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# ========== MOVIE FUNCTIONS ==========
def add_movie(tmdb_id, title, year, quality, file_id, file_size, added_by):
    """Add a movie to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO movies 
            (tmdb_id, title, year, quality, file_id, file_size, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (tmdb_id, title, year, quality, file_id, file_size, added_by))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding movie: {e}")
        return False
    finally:
        conn.close()

def add_movie_quality(tmdb_id, quality, file_id, file_size):
    """Add multiple quality options for same movie"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO movie_qualities (tmdb_id, quality, file_id, file_size)
            VALUES (?, ?, ?, ?)
        ''', (tmdb_id, quality, file_id, file_size))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding quality: {e}")
        return False
    finally:
        conn.close()

def get_movie_by_tmdb(tmdb_id):
    """Get movie details by TMDb ID"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM movies WHERE tmdb_id = ?', (tmdb_id,))
    movie = cursor.fetchone()
    
    # Get all qualities for this movie
    if movie:
        cursor.execute('SELECT quality, file_id, file_size FROM movie_qualities WHERE tmdb_id = ?', (tmdb_id,))
        qualities = cursor.fetchall()
        
        conn.close()
        return {'movie': movie, 'qualities': qualities}
    
    conn.close()
    return None

def search_movies_db(query):
    """Search movies in database by title"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT tmdb_id, title, year FROM movies 
        WHERE title LIKE ? ORDER BY year DESC
    ''', (f'%{query}%',))
    
    results = cursor.fetchall()
    conn.close()
    return results

# ========== USER FUNCTIONS ==========
def add_user(user_id, username, first_name):
    """Add or update user"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    
    conn.commit()
    conn.close()

def increment_user_requests(user_id):
    """Increment user request count"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET total_requests = total_requests + 1 
        WHERE user_id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    """Get user statistics"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    conn.close()
    return user

# ========== REQUEST FUNCTIONS ==========
def add_request(user_id, tmdb_id, movie_title):
    """Add a movie request"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO requests (user_id, tmdb_id, movie_title)
        VALUES (?, ?, ?)
    ''', (user_id, tmdb_id, movie_title))
    
    conn.commit()
    conn.close()

def get_pending_requests():
    """Get all pending requests"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM requests WHERE status = 'pending' 
        ORDER BY request_date DESC
    ''')
    
    requests = cursor.fetchall()
    conn.close()
    return requests

def update_request_status(request_id, status):
    """Update request status"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE requests SET status = ? WHERE id = ?', (status, request_id))
    conn.commit()
    conn.close()

# ========== STATS FUNCTIONS ==========
def get_total_movies():
    """Get total movies count"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM movies')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_users():
    """Get total users count"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_requests():
    """Get total requests count"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM requests')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Initialize database when this file is run
if __name__ == '__main__':
    init_database()