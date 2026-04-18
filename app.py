from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import random
import string
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# Create tables on startup
def init_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            phone VARCHAR(20),
            password VARCHAR(255),
            referral_code VARCHAR(50),
            referral_count INT DEFAULT 0,
            free_credit_claimed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Pending payments table
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
    
    # Pending wins table
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
    
    # Daily rewards table
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
    
    # Game tokens table
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
    print("✅ Tables created/verified")

# ========== USER ROUTES ==========

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    referral_code_input = data.get('referralCode')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if email exists
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Email already registered'})
    
    # Generate referral code
    referral_code = name[:3].upper() + str(random.randint(1000, 9999))
    
    # Insert user
    cur.execute("""
        INSERT INTO users (name, email, phone, password, referral_code) 
        VALUES (%s, %s, %s, %s, %s) 
        RETURNING id, name, email, phone, referral_code, referral_count
    """, (name, email, phone, password, referral_code))
    
    user = cur.fetchone()
    
    # Process referral code if provided
    if referral_code_input:
        cur.execute("UPDATE users SET referral_count = referral_count + 1 WHERE referral_code = %s", (referral_code_input,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    # Convert to dict for JSON response
    user_dict = {'id': user[0], 'name': user[1], 'email': user[2], 'phone': user[3], 'referral_code': user[4], 'referral_count': user[5]}
    return jsonify({'success': True, 'user': user_dict})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
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

@app.route('/api/user/<email>', methods=['GET'])
def get_user(email):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT name, email, referral_code, referral_count FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify(user) if user else jsonify(None)

# ========== PAYMENT ROUTES ==========

@app.route('/api/submit-payment', methods=['POST'])
def submit_payment():
    data = request.json
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

@app.route('/api/admin/pending-payments', methods=['GET'])
def get_pending_payments():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM pending_payments WHERE status = 'pending' ORDER BY id DESC")
    payments = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(payments)

@app.route('/api/admin/approve-payment/<int:payment_id>', methods=['POST'])
def approve_payment(payment_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("UPDATE pending_payments SET status = 'completed' WHERE id = %s RETURNING *", (payment_id,))
    payment = cur.fetchone()
    
    if payment:
        cur.execute("""
            INSERT INTO game_tokens (user_email, reward, amount) 
            VALUES (%s, %s, %s)
        """, (payment['user_email'], payment['reward'], payment['amount']))
    
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/decline-payment/<int:payment_id>', methods=['POST'])
def decline_payment(payment_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pending_payments SET status = 'declined' WHERE id = %s", (payment_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

# ========== WIN ROUTES ==========

@app.route('/api/submit-win', methods=['POST'])
def submit_win():
    data = request.json
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

@app.route('/api/admin/pending-wins', methods=['GET'])
def get_pending_wins():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM pending_wins WHERE status = 'pending' ORDER BY id DESC")
    wins = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(wins)

@app.route('/api/admin/approve-win/<int:win_id>', methods=['POST'])
def approve_win(win_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pending_wins SET status = 'completed' WHERE id = %s", (win_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/decline-win/<int:win_id>', methods=['POST'])
def decline_win(win_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pending_wins SET status = 'declined' WHERE id = %s", (win_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

# ========== DAILY REWARDS ==========

@app.route('/api/submit-daily-reward', methods=['POST'])
def submit_daily_reward():
    data = request.json
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

@app.route('/api/admin/pending-daily-rewards', methods=['GET'])
def get_pending_daily_rewards():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM daily_rewards WHERE status = 'pending' ORDER BY id DESC")
    rewards = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rewards)

@app.route('/api/admin/approve-daily/<int:reward_id>', methods=['POST'])
def approve_daily(reward_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE daily_rewards SET status = 'completed' WHERE id = %s", (reward_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/decline-daily/<int:reward_id>', methods=['POST'])
def decline_daily(reward_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE daily_rewards SET status = 'declined' WHERE id = %s", (reward_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'OnSlot API is running'})

# Initialize tables on startup
init_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)