from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import random
from datetime import datetime

app = Flask(__name__)

# Allow all origins
CORS(app)

# Database connection
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

# Drop and recreate all tables for a COMPLETELY FRESH START
def reset_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Drop all existing tables
        cur.execute("DROP TABLE IF EXISTS referral_rewards CASCADE")
        cur.execute("DROP TABLE IF EXISTS pending_purchases CASCADE")
        cur.execute("DROP TABLE IF EXISTS pending_payments CASCADE")
        cur.execute("DROP TABLE IF EXISTS data_plans CASCADE")
        cur.execute("DROP TABLE IF EXISTS users CASCADE")
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ All tables dropped - Fresh start!")
        return True
    except Exception as e:
        print(f"Error dropping tables: {e}")
        return False

# Create tables on startup
def init_tables():
    try:
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
                referral_reward_claimed BOOLEAN DEFAULT FALSE,
                wallet_balance INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Data plans table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_plans (
                id SERIAL PRIMARY KEY,
                network VARCHAR(20),
                plan_size VARCHAR(20),
                plan_name VARCHAR(100),
                price INT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Pending payments (wallet funding)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                user_phone VARCHAR(20),
                amount INT,
                transaction_ref VARCHAR(100),
                payment_method VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Pending data purchases
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_purchases (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                user_phone VARCHAR(20),
                network VARCHAR(20),
                plan_name VARCHAR(100),
                plan_size VARCHAR(20),
                plan_price INT,
                validity VARCHAR(50),
                phone_number VARCHAR(20),
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Referral Rewards table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_rewards (
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
        
        # Insert default data plans
        cur.execute("SELECT COUNT(*) FROM data_plans")
        if cur.fetchone()[0] == 0:
            default_plans = [
                # MTN Plans
                ('mtn', '500MB', 'MTN 500MB Data', 200),
                ('mtn', '1GB', 'MTN 1GB Data', 350),
                ('mtn', '2GB', 'MTN 2GB Data', 800),
                ('mtn', '3GB', 'MTN 3GB Data', 1200),
                ('mtn', '5GB', 'MTN 5GB Data', 1900),
                # Airtel Plans
                ('airtel', '300MB', 'Airtel 300MB Data', 200),
                ('airtel', '600MB', 'Airtel 600MB Data', 300),
                ('airtel', '1.5GB', 'Airtel 1.5GB Data', 350),
                ('airtel', '2GB', 'Airtel 2GB Data', 400),
                ('airtel', '6GB', 'Airtel 6GB Data', 2600),
                ('airtel', '10GB', 'Airtel 10GB Data', 399),
                # Glo Plans
                ('glo', '200MB', 'Glo 200MB Data', 99),
                ('glo', '500MB', 'Glo 500MB Data', 200),
                ('glo', '1GB', 'Glo 1GB Data', 350),
                ('glo', '2GB', 'Glo 2GB Data', 700),
                ('glo', '5GB', 'Glo 5GB Data', 1500),
                ('glo', '10GB', 'Glo 10GB Data', 2500),
                # 9mobile Plans
                ('9mobile', '250MB', '9mobile 250MB Data', 100),
                ('9mobile', '500MB', '9mobile 500MB Data', 200),
                ('9mobile', '1GB', '9mobile 1GB Data', 450),
                ('9mobile', '2GB', '9mobile 2GB Data', 800),
                ('9mobile', '5.2GB', '9mobile 5.2GB Data', 2300),
                ('9mobile', '11.4GB', '9mobile 11.4GB Data', 5000),
            ]
            for plan in default_plans:
                cur.execute("""
                    INSERT INTO data_plans (network, plan_size, plan_name, price) 
                    VALUES (%s, %s, %s, %s)
                """, plan)
            print("✅ Default data plans inserted")
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Tables created successfully!")
        return True
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False

# Reset and initialize
reset_tables()
init_tables()

# ============ CREATE ADMIN USER ENDPOINT ============
@app.route('/api/create-admin', methods=['POST'])
def create_admin():
    data = request.json
    name = data.get('name', 'Admin')
    email = data.get('email')
    phone = data.get('phone', '08012345678')
    password = data.get('password', 'admin123')
    
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'})
    
    # Auto-add %% if not present for admin creation
    if not email.endswith('%%'):
        email = email + '%%'
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'User already exists'})
        
        referral_code = name[:3].upper() + str(random.randint(1000, 9999))
        
        cur.execute("""
            INSERT INTO users (name, email, phone, password, referral_code, wallet_balance) 
            VALUES (%s, %s, %s, %s, %s, %s) 
            RETURNING id, name, email, phone, referral_code, referral_count, wallet_balance, referral_reward_claimed
        """, (name, email, phone, password, referral_code, 1000))
        
        user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        user_dict = {
            'id': user[0], 'name': user[1], 'email': user[2], 'phone': user[3], 
            'referral_code': user[4], 'referral_count': user[5], 'wallet_balance': user[6],
            'referral_reward_claimed': user[7]
        }
        return jsonify({'success': True, 'user': user_dict, 'message': f'Admin {email} created!'})
    except Exception as e:
        print(f"Create admin error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============ USER AUTHENTICATION ============

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
            RETURNING id, name, email, phone, referral_code, referral_count, wallet_balance, referral_reward_claimed
        """, (name, email, phone, password, referral_code))
        
        user = cur.fetchone()
        
        if referral_code_input:
            cur.execute("UPDATE users SET referral_count = referral_count + 1 WHERE referral_code = %s", (referral_code_input,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        user_dict = {
            'id': user[0], 'name': user[1], 'email': user[2], 'phone': user[3], 
            'referral_code': user[4], 'referral_count': user[5], 'wallet_balance': user[6],
            'referral_reward_claimed': user[7]
        }
        return jsonify({'success': True, 'user': user_dict})
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'success': False, 'error': str(e)})

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
            print(f"✅ User logged in: {email}")
            return jsonify({'success': True, 'user': user})
        else:
            print(f"❌ Login failed for: {email}")
            return jsonify({'success': False, 'error': 'Invalid credentials'})
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/<email>', methods=['GET'])
def get_user(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name, email, referral_code, referral_count, wallet_balance, referral_reward_claimed FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify(user) if user else jsonify(None)
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify(None)

# ============ DATA PLANS ============

@app.route('/api/data-plans', methods=['GET'])
def get_data_plans():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM data_plans WHERE is_active = true ORDER BY network, price")
        plans = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(plans)
    except Exception as e:
        print(f"Get data plans error: {e}")
        return jsonify([])

# ============ WALLET FUNDING ============

@app.route('/api/submit-funding', methods=['POST'])
def submit_funding():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pending_payments (user_email, user_name, user_phone, amount, transaction_ref, payment_method) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (data.get('userEmail'), data.get('userName'), data.get('userPhone'), 
              data.get('amount'), data.get('transactionRef'), data.get('paymentMethod')))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Submit funding error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/pending-funding', methods=['GET'])
def get_pending_funding():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pending_payments WHERE status = 'pending' ORDER BY id DESC")
        payments = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(payments)
    except Exception as e:
        print(f"Get pending funding error: {e}")
        return jsonify([])

@app.route('/api/admin/approve-funding/<int:payment_id>', methods=['POST'])
def approve_funding(payment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM pending_payments WHERE id = %s", (payment_id,))
        payment = cur.fetchone()
        
        if payment:
            cur.execute("UPDATE pending_payments SET status = 'completed' WHERE id = %s", (payment_id,))
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", (payment[4], payment[1]))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve funding error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/decline-funding/<int:payment_id>', methods=['POST'])
def decline_funding(payment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_payments SET status = 'declined' WHERE id = %s", (payment_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline funding error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============ DATA PURCHASE ============

@app.route('/api/submit-purchase', methods=['POST'])
def submit_purchase():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT wallet_balance FROM users WHERE email = %s", (data.get('userEmail'),))
        result = cur.fetchone()
        balance = result[0] if result else 0
        
        if balance < data.get('totalAmount'):
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Insufficient wallet balance'})
        
        cur.execute("UPDATE users SET wallet_balance = wallet_balance - %s WHERE email = %s", 
                   (data.get('totalAmount'), data.get('userEmail')))
        
        cur.execute("""
            INSERT INTO pending_purchases (user_email, user_name, user_phone, network, plan_name, plan_size, plan_price, validity, phone_number) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (data.get('userEmail'), data.get('userName'), data.get('userPhone'),
              data.get('network'), data.get('planName'), data.get('planSize'), 
              data.get('planPrice'), data.get('validity'), data.get('phoneNumber')))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Submit purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/pending-purchases', methods=['GET'])
def get_pending_purchases():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pending_purchases WHERE status = 'pending' ORDER BY id DESC")
        purchases = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(purchases)
    except Exception as e:
        print(f"Get pending purchases error: {e}")
        return jsonify([])

@app.route('/api/admin/approve-purchase/<int:purchase_id>', methods=['POST'])
def approve_purchase(purchase_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_purchases SET status = 'completed' WHERE id = %s", (purchase_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/decline-purchase/<int:purchase_id>', methods=['POST'])
def decline_purchase(purchase_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM pending_purchases WHERE id = %s", (purchase_id,))
        purchase = cur.fetchone()
        
        if purchase:
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", (purchase[7], purchase[1]))
            cur.execute("UPDATE pending_purchases SET status = 'declined' WHERE id = %s", (purchase_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============ REFERRAL REWARDS ============

@app.route('/api/submit-referral-reward', methods=['POST'])
def submit_referral_reward():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO referral_rewards (user_email, user_name, phone, network, amount) 
            VALUES (%s, %s, %s, %s, %s)
        """, (data.get('userEmail'), data.get('userName'), data.get('phone'), 
              data.get('network'), data.get('amount')))
        cur.execute("UPDATE users SET referral_reward_claimed = true WHERE email = %s", (data.get('userEmail'),))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Submit referral reward error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/pending-referrals', methods=['GET'])
def get_pending_referrals():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM referral_rewards WHERE status = 'pending' ORDER BY id DESC")
        rewards = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(rewards)
    except Exception as e:
        print(f"Get pending referrals error: {e}")
        return jsonify([])

@app.route('/api/admin/approve-referral/<int:reward_id>', methods=['POST'])
def approve_referral(reward_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM referral_rewards WHERE id = %s", (reward_id,))
        reward = cur.fetchone()
        
        if reward:
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", (reward[5], reward[1]))
            cur.execute("UPDATE referral_rewards SET status = 'completed' WHERE id = %s", (reward_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve referral error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/decline-referral/<int:reward_id>', methods=['POST'])
def decline_referral(reward_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE referral_rewards SET status = 'declined' WHERE id = %s", (reward_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline referral error: {e}")
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/debug-users', methods=['GET'])
def debug_users():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name, email, password, wallet_balance FROM users")
        users = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/fix-login', methods=['POST'])
def fix_login():
    """Fix login issues - reset user password"""
    data = request.json
    email = data.get('email')
    new_password = data.get('password', 'admin123')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': f'Password reset for {email}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)