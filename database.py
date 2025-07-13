import sqlite3
import json
from typing import List, Dict, Optional
from config import DATABASE_PATH

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    coin_ticker TEXT,
                    threshold_type TEXT,
                    threshold_price REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Auto alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_alerts (
                    user_id INTEGER,
                    coin_ticker TEXT,
                    enabled INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, coin_ticker),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
    
    def add_user(self, user_id: int, username: str, first_name: str) -> bool:
        """Add new user to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, username, first_name)
                    VALUES (?, ?, ?)
                ''', (user_id, username, first_name))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by user_id"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                user = cursor.fetchone()
                if user:
                    return {
                        'user_id': user[0],
                        'username': user[1],
                        'first_name': user[2],
                        'created_at': user[3]
                    }
                return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    def add_alert(self, user_id: int, coin_ticker: str, threshold_type: str, threshold_price: float) -> bool:
        """Add new price alert"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts (user_id, coin_ticker, threshold_type, threshold_price)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, coin_ticker.upper(), threshold_type, threshold_price))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding alert: {e}")
            return False
    
    def get_user_alerts(self, user_id: int) -> List[Dict]:
        """Get all alerts for a user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM alerts WHERE user_id = ? ORDER BY created_at DESC
                ''', (user_id,))
                alerts = cursor.fetchall()
                return [
                    {
                        'id': alert[0],
                        'user_id': alert[1],
                        'coin_ticker': alert[2],
                        'threshold_type': alert[3],
                        'threshold_price': alert[4],
                        'created_at': alert[5]
                    }
                    for alert in alerts
                ]
        except Exception as e:
            print(f"Error getting alerts: {e}")
            return []
    
    def delete_alert(self, alert_id: int, user_id: int) -> bool:
        """Delete specific alert"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM alerts WHERE id = ? AND user_id = ?
                ''', (alert_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting alert: {e}")
            return False
    
    def get_all_alerts(self) -> List[Dict]:
        """Get all alerts for monitoring"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.*, u.username, u.first_name 
                    FROM alerts a 
                    JOIN users u ON a.user_id = u.user_id
                    ORDER BY a.created_at DESC
                ''')
                alerts = cursor.fetchall()
                return [
                    {
                        'id': alert[0],
                        'user_id': alert[1],
                        'coin_ticker': alert[2],
                        'threshold_type': alert[3],
                        'threshold_price': alert[4],
                        'created_at': alert[5],
                        'username': alert[6],
                        'first_name': alert[7]
                    }
                    for alert in alerts
                ]
        except Exception as e:
            print(f"Error getting all alerts: {e}")
            return []
    
    def get_all_users(self) -> List[Dict]:
        """Get all registered users"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id, username, first_name FROM users')
                users = cursor.fetchall()
                return [
                    {
                        'user_id': user[0],
                        'username': user[1],
                        'first_name': user[2]
                    }
                    for user in users
                ]
        except Exception as e:
            print(f"Error getting all users: {e}")
            return [] 

    def set_auto_alert(self, user_id: int, coin_ticker: str, enabled: bool):
        """Enable or disable auto alert for a coin for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO auto_alerts (user_id, coin_ticker, enabled)
                VALUES (?, ?, ?)
            ''', (user_id, coin_ticker.upper(), int(enabled)))
            conn.commit()

    def get_auto_alerts(self, user_id: int):
        """Get all auto-alert coins for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT coin_ticker, enabled FROM auto_alerts WHERE user_id = ?
            ''', (user_id,))
            return cursor.fetchall()

    def remove_auto_alert(self, user_id: int, coin_ticker: str):
        """Remove auto alert for a coin for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM auto_alerts WHERE user_id = ? AND coin_ticker = ?
            ''', (user_id, coin_ticker.upper()))
            conn.commit() 

    def set_global_auto_alert(self, user_id: int, enabled: bool):
        """Enable/disable global auto-alert for all popular coins for a user"""
        coins = ["BTC", "ETH", "SOL", "BNB", "ADA", "XRP", "DOGE", "MATIC"]
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for coin in coins:
                cursor.execute('''
                    INSERT OR REPLACE INTO auto_alerts (user_id, coin_ticker, enabled)
                    VALUES (?, ?, ?)
                ''', (user_id, coin, int(enabled)))
            conn.commit()

    def is_global_auto_alert_enabled(self, user_id: int):
        """Check if global auto-alert is enabled for all popular coins for a user"""
        coins = ["BTC", "ETH", "SOL", "BNB", "ADA", "XRP", "DOGE", "MATIC"]
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM auto_alerts WHERE user_id = ? AND coin_ticker IN ({}) AND enabled = 1
            '''.format(','.join(['?']*len(coins))), [user_id] + coins)
            count = cursor.fetchone()[0]
            return count == len(coins) 