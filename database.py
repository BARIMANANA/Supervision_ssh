import sqlite3
import datetime
import json

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('ssh_sessions.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        # Table des sessions SSH
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_host TEXT NOT NULL,
                client_port INTEGER,
                username TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Table des commandes exécutées
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                command TEXT NOT NULL,
                result TEXT,
                execution_time TEXT NOT NULL,
                duration REAL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        
        self.conn.commit()
    
    def log_session_start(self, client_host, client_port, username):
        start_time = datetime.datetime.now().isoformat()
        self.cursor.execute('''
            INSERT INTO sessions (client_host, client_port, username, start_time, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (client_host, client_port, username, start_time, 'active'))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def log_session_end(self, session_id):
        end_time = datetime.datetime.now().isoformat()
        self.cursor.execute('''
            UPDATE sessions SET end_time = ?, status = 'closed'
            WHERE id = ?
        ''', (end_time, session_id))
        self.conn.commit()
    
    def log_command(self, session_id, command, result, duration):
        execution_time = datetime.datetime.now().isoformat()
        self.cursor.execute('''
            INSERT INTO command_history (session_id, command, result, execution_time, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, command, result, execution_time, duration))
        self.conn.commit()
    
    def get_session_history(self):
        self.cursor.execute('''
            SELECT id, client_host, client_port, username, start_time, end_time, status
            FROM sessions ORDER BY start_time DESC
        ''')
        return self.cursor.fetchall()
    
    def get_command_history(self, session_id=None):
        if session_id:
            self.cursor.execute('''
                SELECT id, command, result, execution_time, duration
                FROM command_history WHERE session_id = ?
                ORDER BY execution_time DESC
            ''', (session_id,))
        else:
            self.cursor.execute('''
                SELECT id, command, result, execution_time, duration
                FROM command_history ORDER BY execution_time DESC
            ''')
        return self.cursor.fetchall()
    
    def close(self):
        self.conn.close()