from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Get Database URL from environment variable (Render will set this)
DATABASE_URL = os.environ.get('DATABASE_URL')

print(f"Database URL loaded: {'Yes' if DATABASE_URL else 'No'}")

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable not set!")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise e

# Create tables on startup
def init_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100) UNIQUE,
                phone VARCHAR(20),
                password VARCHAR(255),
                referral_code VARCHAR(50),
                referral_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                user_phone VARCHAR(20),
                amount VARCHAR(20),
                reward VARCHAR(50),
                transaction_ref VARCHAR(100),
                payment_method VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_wins (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                user_phone VARCHAR(20),
                network VARCHAR(20),
                reward VARCHAR(50),
                amount_paid VARCHAR(20),
                score INT,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_rewards (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                phone VARCHAR(20),
                network VARCHAR(20),
                amount INT,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_tokens (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                reward VARCHAR(50),
                amount VARCHAR(20),
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")

# Root route
@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'ok', 'message': 'OnSlot API is running. Use /api/health to check status.'})

# Health check
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'OnSlot API is running'})

# Signup
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    referral_code_input = data.get('referralCode')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Email already registered'})
        
        referral_code = name[:3].upper() + str(random.randint(1000, 9999))
        
        cur.execute("""
            INSERT INTO users (name, email, phone, password, referral_code) 
            VALUES (%s, %s, %s, %s, %s) 
            RETURNING id, name, email, phone, referral_code, referral_count
        """, (name, email, phone, password, referral_code))
        
        user = cur.fetchone()
        
        if referral_code_input:
            cur.execute("UPDATE users SET referral_count = referral_count + 1 WHERE referral_code = %s", (referral_code_input,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        user_dict = {'id': user[0], 'name': user[1], 'email': user[2], 'phone': user[3], 'referral_code': user[4], 'referral_count': user[5]}
        return jsonify({'success': True, 'user': user_dict})
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Login
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'error': 'Invalid credentials'})
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Get user
@app.route('/api/user/<email>', methods=['GET'])
def get_user(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name, email, referral_code, referral_count FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify(user) if user else jsonify(None)
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify(None)

# Submit payment
@app.route('/api/submit-payment', methods=['POST'])
def submit_payment():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pending_payments (user_email, user_name, user_phone, amount, reward, transaction_ref, payment_method) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data.get('userEmail'), data.get('userName'), data.get('userPhone'), 
              data.get('amount'), data.get('reward'), data.get('transactionRef'), data.get('paymentMethod')))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Submit payment error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Admin: Get pending payments
@app.route('/api/admin/pending-payments', methods=['GET'])
def get_pending_payments():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pending_payments WHERE status = 'pending' ORDER BY id DESC")
        payments = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(payments)
    except Exception as e:
        print(f"Get pending payments error: {e}")
        return jsonify([])

# Admin: Approve payment
@app.route('/api/admin/approve-payment/<int:payment_id>', methods=['POST'])
def approve_payment(payment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_payments SET status = 'completed' WHERE id = %s", (payment_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve payment error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Admin: Decline payment
@app.route('/api/admin/decline-payment/<int:payment_id>', methods=['POST'])
def decline_payment(payment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_payments SET status = 'declined' WHERE id = %s", (payment_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline payment error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Submit win
@app.route('/api/submit-win', methods=['POST'])
def submit_win():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pending_wins (user_email, user_name, user_phone, network, reward, amount_paid, score) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data.get('userEmail'), data.get('userName'), data.get('userPhone'),
              data.get('network'), data.get('reward'), data.get('amountPaid'), data.get('score')))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Submit win error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Admin: Get pending wins
@app.route('/api/admin/pending-wins', methods=['GET'])
def get_pending_wins():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pending_wins WHERE status = 'pending' ORDER BY id DESC")
        wins = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(wins)
    except Exception as e:
        print(f"Get pending wins error: {e}")
        return jsonify([])

# Admin: Approve win
@app.route('/api/admin/approve-win/<int:win_id>', methods=['POST'])
def approve_win(win_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_wins SET status = 'completed' WHERE id = %s", (win_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve win error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Admin: Decline win
@app.route('/api/admin/decline-win/<int:win_id>', methods=['POST'])
def decline_win(win_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_wins SET status = 'declined' WHERE id = %s", (win_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline win error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Submit daily reward
@app.route('/api/submit-daily-reward', methods=['POST'])
def submit_daily_reward():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO daily_rewards (user_email, user_name, phone, network, amount) 
            VALUES (%s, %s, %s, %s, %s)
        """, (data.get('userEmail'), data.get('userName'), data.get('phone'),
              data.get('network'), data.get('amount')))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Submit daily reward error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Admin: Get pending daily rewards
@app.route('/api/admin/pending-daily-rewards', methods=['GET'])
def get_pending_daily_rewards():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM daily_rewards WHERE status = 'pending' ORDER BY id DESC")
        rewards = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rewards)
    except Exception as e:
        print(f"Get daily rewards error: {e}")
        return jsonify([])

# Admin: Approve daily reward
@app.route('/api/admin/approve-daily/<int:reward_id>', methods=['POST'])
def approve_daily(reward_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE daily_rewards SET status = 'completed' WHERE id = %s", (reward_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve daily error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Admin: Decline daily reward
@app.route('/api/admin/decline-daily/<int:reward_id>', methods=['POST'])
def decline_daily(reward_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE daily_rewards SET status = 'declined' WHERE id = %s", (reward_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline daily error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Initialize tables
init_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)