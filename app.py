from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import random
import hashlib
import re
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=["https://onslot.onrender.com", "http://localhost:5000", "http://127.0.0.1:5500", "*"])

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable not set!")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise e

def init_database():
    """Initialize database tables"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                phone VARCHAR(20) NOT NULL,
                password VARCHAR(255) NOT NULL,
                referral_code VARCHAR(50) UNIQUE,
                referral_count INT DEFAULT 0,
                referral_reward_claimed BOOLEAN DEFAULT FALSE,
                wallet_balance INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Data plans table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_plans (
                id SERIAL PRIMARY KEY,
                network VARCHAR(20) NOT NULL,
                plan_size VARCHAR(20) NOT NULL,
                plan_name VARCHAR(100) NOT NULL,
                price INT NOT NULL,
                validity VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Pending payments table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100) NOT NULL,
                user_name VARCHAR(100) NOT NULL,
                user_phone VARCHAR(20),
                amount INT NOT NULL,
                service_charge INT DEFAULT 50,
                transaction_ref VARCHAR(100) UNIQUE,
                payment_method VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Pending purchases table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_purchases (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100) NOT NULL,
                user_name VARCHAR(100) NOT NULL,
                user_phone VARCHAR(20),
                network VARCHAR(20) NOT NULL,
                plan_size VARCHAR(20) NOT NULL,
                plan_price INT NOT NULL,
                service_charge INT DEFAULT 50,
                validity VARCHAR(50),
                phone_number VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Referral rewards table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_rewards (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100) NOT NULL,
                user_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                network VARCHAR(20) NOT NULL,
                amount INT DEFAULT 400,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default data plans
        cur.execute("SELECT COUNT(*) FROM data_plans")
        if cur.fetchone()[0] == 0:
            default_plans = [
                ('mtn', '500MB', 'MTN 500MB Data', 200, '7 days'),
                ('mtn', '1GB', 'MTN 1GB Data', 350, '7 days'),
                ('mtn', '2GB', 'MTN 2GB Data', 800, '7 days'),
                ('mtn', '3GB', 'MTN 3GB Data', 1200, '30 days'),
                ('mtn', '5GB', 'MTN 5GB Data', 1900, '30 days'),
                ('mtn', '10GB', 'MTN 10GB Data', 3500, '30 days'),
                ('airtel', '300MB', 'Airtel 300MB Data', 200, '2 days'),
                ('airtel', '600MB', 'Airtel 600MB Data', 300, '2 days'),
                ('airtel', '1.5GB', 'Airtel 1.5GB Data', 350, '2 days'),
                ('airtel', '2GB', 'Airtel 2GB Data', 400, '2 days'),
                ('airtel', '6GB', 'Airtel 6GB Data', 2600, '7 days'),
                ('airtel', '10GB', 'Airtel 10GB Data', 4000, '30 days'),
                ('glo', '200MB', 'Glo 200MB Data', 99, '2 days'),
                ('glo', '500MB', 'Glo 500MB Data', 200, '2 days'),
                ('glo', '1GB', 'Glo 1GB Data', 350, '7 days'),
                ('glo', '2GB', 'Glo 2GB Data', 700, '7 days'),
                ('glo', '5GB', 'Glo 5GB Data', 1500, '7 days'),
                ('glo', '10GB', 'Glo 10GB Data', 2800, '30 days'),
                ('9mobile', '250MB', '9mobile 250MB Data', 100, '7 days'),
                ('9mobile', '500MB', '9mobile 500MB Data', 200, '7 days'),
                ('9mobile', '1GB', '9mobile 1GB Data', 450, '7 days'),
                ('9mobile', '2GB', '9mobile 2GB Data', 800, '7 days'),
                ('9mobile', '5.2GB', '9mobile 5.2GB Data', 2300, '30 days'),
                ('9mobile', '11.4GB', '9mobile 11.4GB Data', 5000, '30 days'),
            ]
            for plan in default_plans:
                cur.execute("""
                    INSERT INTO data_plans (network, plan_size, plan_name, price, validity) 
                    VALUES (%s, %s, %s, %s, %s)
                """, plan)
            print("✅ Default data plans inserted")
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database initialized successfully!")
        return True
    except Exception as e:
        print(f"Database initialization error: {e}")
        return False

# ============ ROOT ROUTE ============

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'message': 'OnSlot API is running',
        'endpoints': [
            '/api/signup',
            '/api/login',
            '/api/user/<email>',
            '/api/data-plans',
            '/api/submit-funding',
            '/api/submit-purchase',
            '/api/submit-referral-reward',
            '/api/admin/pending-funding',
            '/api/admin/pending-purchases',
            '/api/admin/pending-referrals',
            '/api/health'
        ]
    })

# ============ USER AUTHENTICATION ============

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        referral_code_input = data.get('referralCode', '').strip()
        
        # Validation
        if not all([name, email, phone, password]):
            return jsonify({'success': False, 'error': 'All fields are required'})
        
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email.replace('%%', '')):
            return jsonify({'success': False, 'error': 'Invalid email format'})
        
        if len(password) < 4:
            return jsonify({'success': False, 'error': 'Password must be at least 4 characters'})
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Email already registered'})
        
        # Generate unique referral code
        referral_code = name[:3].upper() + str(random.randint(1000, 9999))
        hashed_password = hash_password(password)
        
        cur.execute("""
            INSERT INTO users (name, email, phone, password, referral_code) 
            VALUES (%s, %s, %s, %s, %s) 
            RETURNING id, name, email, phone, referral_code, referral_count, wallet_balance
        """, (name, email, phone, hashed_password, referral_code))
        
        user = cur.fetchone()
        
        # Process referral if provided
        if referral_code_input:
            cur.execute("""
                UPDATE users 
                SET referral_count = referral_count + 1 
                WHERE referral_code = %s AND email != %s
            """, (referral_code_input, email))
            conn.commit()
            
            # Check if referrer reached 5 referrals
            cur.execute("""
                SELECT email, referral_count, referral_reward_claimed 
                FROM users WHERE referral_code = %s
            """, (referral_code_input,))
            referrer = cur.fetchone()
            
            if referrer and referrer[1] >= 5 and not referrer[2]:
                cur.execute("SELECT name FROM users WHERE referral_code = %s", (referral_code_input,))
                referrer_name = cur.fetchone()
                cur.execute("""
                    INSERT INTO referral_rewards (user_email, user_name, phone, network, amount) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (referrer[0], referrer_name[0] if referrer_name else '', '', '', 400))
                conn.commit()
        
        user_dict = {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'phone': user[3],
            'referral_code': user[4],
            'referral_count': user[5],
            'wallet_balance': user[6]
        }
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'user': user_dict, 'message': 'Account created successfully!'})
    
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'})
        
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
        print(f"Login error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/<email>', methods=['GET'])
def get_user(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, email, phone, referral_code, referral_count, 
                   wallet_balance, referral_reward_claimed, created_at
            FROM users WHERE email = %s
        """, (email,))
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
    try:
        data = request.json
        user_email = data.get('userEmail', '').strip().lower()
        user_name = data.get('userName', '').strip()
        user_phone = data.get('userPhone', '').strip()
        amount = data.get('amount', 0)
        service_charge = data.get('serviceCharge', 50)
        transaction_ref = data.get('transactionRef', '').strip()
        payment_method = data.get('paymentMethod', 'bank_transfer')
        
        if not all([user_email, user_name, transaction_ref]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        if amount < 400:
            return jsonify({'success': False, 'error': 'Minimum funding amount is ₦400'})
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM pending_payments WHERE transaction_ref = %s", (transaction_ref,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Transaction reference already used'})
        
        cur.execute("""
            INSERT INTO pending_payments 
            (user_email, user_name, user_phone, amount, service_charge, transaction_ref, payment_method) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_email, user_name, user_phone, amount, service_charge, transaction_ref, payment_method))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Funding request submitted successfully'})
    
    except Exception as e:
        print(f"Submit funding error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============ DATA PURCHASE ============

@app.route('/api/submit-purchase', methods=['POST'])
def submit_purchase():
    try:
        data = request.json
        user_email = data.get('userEmail', '').strip().lower()
        user_name = data.get('userName', '').strip()
        user_phone = data.get('userPhone', '').strip()
        network = data.get('network', '').strip()
        plan_size = data.get('planSize', '').strip()
        plan_price = data.get('planPrice', 0)
        service_charge = data.get('serviceCharge', 50)
        validity = data.get('validity', '')
        phone_number = data.get('phoneNumber', '').strip()
        
        if not all([user_email, network, plan_size, phone_number]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        total_amount = plan_price + service_charge
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT wallet_balance FROM users WHERE email = %s", (user_email,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'})
        
        balance = result[0]
        
        if balance < total_amount:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Insufficient balance. Need ₦{total_amount}'})
        
        cur.execute("UPDATE users SET wallet_balance = wallet_balance - %s WHERE email = %s", 
                   (total_amount, user_email))
        
        cur.execute("""
            INSERT INTO pending_purchases 
            (user_email, user_name, user_phone, network, plan_size, plan_price, service_charge, validity, phone_number) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_email, user_name, user_phone, network, plan_size, plan_price, service_charge, validity, phone_number))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Purchase request submitted successfully'})
    
    except Exception as e:
        print(f"Submit purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============ REFERRAL REWARDS ============

@app.route('/api/submit-referral-reward', methods=['POST'])
def submit_referral_reward():
    try:
        data = request.json
        user_email = data.get('userEmail', '').strip().lower()
        user_name = data.get('userName', '').strip()
        phone = data.get('phone', '').strip()
        network = data.get('network', '').strip()
        amount = data.get('amount', 400)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT referral_reward_claimed FROM users WHERE email = %s", (user_email,))
        result = cur.fetchone()
        
        if result and result[0]:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Reward already claimed'})
        
        cur.execute("""
            INSERT INTO referral_rewards (user_email, user_name, phone, network, amount) 
            VALUES (%s, %s, %s, %s, %s)
        """, (user_email, user_name, phone, network, amount))
        
        cur.execute("UPDATE users SET referral_reward_claimed = true WHERE email = %s", (user_email,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Referral reward request submitted'})
    
    except Exception as e:
        print(f"Submit referral reward error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============ ADMIN ENDPOINTS ============

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
        
        cur.execute("SELECT * FROM pending_payments WHERE id = %s AND status = 'pending'", (payment_id,))
        payment = cur.fetchone()
        
        if payment:
            total_amount = payment[4] + payment[5]
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", 
                       (total_amount, payment[1]))
            cur.execute("UPDATE pending_payments SET status = 'completed' WHERE id = %s", (payment_id,))
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
        
        cur.execute("SELECT * FROM pending_purchases WHERE id = %s AND status = 'pending'", (purchase_id,))
        purchase = cur.fetchone()
        
        if purchase:
            total_amount = purchase[6] + purchase[7]
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", 
                       (total_amount, purchase[1]))
            cur.execute("UPDATE pending_purchases SET status = 'declined' WHERE id = %s", (purchase_id,))
            conn.commit()
        
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline purchase error: {e}")
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
        
        cur.execute("SELECT * FROM referral_rewards WHERE id = %s AND status = 'pending'", (reward_id,))
        reward = cur.fetchone()
        
        if reward:
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", 
                       (reward[6], reward[1]))
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

# ============ HEALTH CHECK ============

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# ============ INITIALIZE DATABASE ON STARTUP ============
print("🔄 Initializing database...")
init_database()
print("✅ Database initialization complete!")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)