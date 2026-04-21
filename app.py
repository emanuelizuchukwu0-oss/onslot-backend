from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import hashlib

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Create tables if they don't exist"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                phone VARCHAR(20) NOT NULL,
                password VARCHAR(255) NOT NULL,
                wallet_balance INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database tables created/verified!")
    except Exception as e:
        print(f"⚠️ Database init error: {e}")

# Create tables when app starts
init_db()

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "OnSlot API is running!"})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        
        if not all([name, email, phone, password]):
            return jsonify({'success': False, 'error': 'All fields required'})
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Email already registered'})
        
        hashed = hash_password(password)
        
        cur.execute("""
            INSERT INTO users (name, email, phone, password) 
            VALUES (%s, %s, %s, %s)
            RETURNING id, name, email, phone, wallet_balance
        """, (name, email, phone, hashed))
        
        user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'user': {
            'id': user[0], 'name': user[1], 'email': user[2],
            'phone': user[3], 'wallet_balance': user[4]
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if not user:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid email or password'})
        
        if user['password'] != hash_password(password):
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid email or password'})
        
        del user['password']
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'user': user})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)