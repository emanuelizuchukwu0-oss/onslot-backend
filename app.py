from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import random
from datetime import datetime

app = Flask(__name__)

# Allow all origins - this fixes CORS issues for all devices
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

# Create tables on startup
def init_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Users table with free_credit_claimed column
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
            CREATE TABLE IF NOT EXISTS game_tokens (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                reward VARCHAR(50),
                amount VARCHAR(20),
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # ============================================
        # FREE CREDITS TABLE - NEW
        # ============================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS free_credits (
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
        
        # ============================================
        # FIX STUCK TOKENS - RUNS ON EVERY SERVER START
        # ============================================
        # Mark all unused tokens as used (fixes stuck tokens from failed games)
        cur.execute("UPDATE game_tokens SET used = true WHERE used = false")
        fixed_count = cur.rowcount
        print(f"✅ Fixed {fixed_count} stuck tokens")
        
        conn.commit()
        cur.close()
        conn.close()
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")

# Routes
@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'ok', 'message': 'OnSlot API is running. Use /api/health to check status.'})

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'OnSlot API is running'})

# ============================================
# FIX STUCK TOKENS - MANUAL ENDPOINT
# Visit this URL in your browser to fix tokens
# ============================================
@app.route('/api/fix-tokens', methods=['GET'])
def fix_all_tokens():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE game_tokens SET used = true WHERE used = false")
        count = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': f'Fixed {count} stuck tokens', 'fixed_count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Get free credit count
@app.route('/api/free-credit-count', methods=['GET'])
def get_free_credit_count():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE free_credit_claimed = true")
        claimed_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        # Maximum 5 users can get free credit
        max_free_users = 5
        spots_left = max_free_users - claimed_count
        return jsonify({'claimedCount': claimed_count, 'spotsLeft': spots_left if spots_left > 0 else 0})
    except Exception as e:
        print(f"Free credit count error: {e}")
        return jsonify({'claimedCount': 0, 'spotsLeft': 5})

# ============================================
# FREE CREDIT REQUESTS - NEW
# ============================================

@app.route('/api/submit-free-credit', methods=['POST'])
def submit_free_credit():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO free_credits (user_email, user_name, phone, network, amount) 
            VALUES (%s, %s, %s, %s, %s)
        """, (data.get('userEmail'), data.get('userName'), data.get('phone'),
              data.get('network'), data.get('amount')))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Submit free credit error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mark-free-credit-claimed', methods=['POST'])
def mark_free_credit_claimed():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET free_credit_claimed = true WHERE email = %s", (data.get('userEmail'),))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Mark free credit claimed error: {e}")
        return jsonify({'success': False})

@app.route('/api/admin/free-credits', methods=['GET'])
def get_free_credits():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM free_credits WHERE status = 'pending' ORDER BY id DESC")
        credits = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(credits)
    except Exception as e:
        print(f"Get free credits error: {e}")
        return jsonify([])

@app.route('/api/admin/approve-free-credit/<int:credit_id>', methods=['POST'])
def approve_free_credit(credit_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE free_credits SET status = 'completed' WHERE id = %s", (credit_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve free credit error: {e}")
        return jsonify({'success': False})

@app.route('/api/admin/decline-free-credit/<int:credit_id>', methods=['POST'])
def decline_free_credit(credit_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE free_credits SET status = 'declined' WHERE id = %s", (credit_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline free credit error: {e}")
        return jsonify({'success': False})

# ============================================
# GAME TOKEN ENDPOINTS
# ============================================

# Check if user has a game token
@app.route('/api/user-game-token/<email>', methods=['GET'])
def get_user_game_token(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM game_tokens WHERE user_email = %s AND used = false ORDER BY id DESC LIMIT 1", (email,))
        token = cur.fetchone()
        cur.close()
        conn.close()
        
        if token:
            return jsonify({'hasToken': True, 'reward': token['reward'], 'amount': token['amount'], 'tokenId': token['id']})
        else:
            return jsonify({'hasToken': False})
    except Exception as e:
        print(f"Get game token error: {e}")
        return jsonify({'hasToken': False})

@app.route('/api/use-game-token/<int:token_id>', methods=['POST'])
def use_game_token(token_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE game_tokens SET used = true WHERE id = %s", (token_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Use game token error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# USER AUTHENTICATION
# ============================================

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
        
        # Check if this user gets free credit (maximum 5 users)
        cur.execute("SELECT COUNT(*) FROM users WHERE free_credit_claimed = true")
        claimed_count = cur.fetchone()[0]
        MAX_FREE_USERS = 5
        
        got_free_credit = False
        if claimed_count < MAX_FREE_USERS:
            got_free_credit = True
            cur.execute("UPDATE users SET free_credit_claimed = true WHERE id = %s", (user[0],))
        
        conn.commit()
        cur.close()
        conn.close()
        
        user_dict = {
            'id': user[0], 'name': user[1], 'email': user[2], 'phone': user[3], 
            'referral_code': user[4], 'referral_count': user[5], 'got_free_credit': got_free_credit
        }
        return jsonify({'success': True, 'user': user_dict})
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cleanup-tokens/<email>', methods=['POST'])
def cleanup_tokens(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE game_tokens SET used = true WHERE user_email = %s AND used = false AND created_at < NOW() - INTERVAL '1 hour'", (email,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Cleanup error: {e}")
        return jsonify({'success': False})

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

@app.route('/api/user/<email>', methods=['GET'])
def get_user(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name, email, referral_code, referral_count, free_credit_claimed FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify(user) if user else jsonify(None)
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify(None)

# ============================================
# PAYMENT ROUTES
# ============================================

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

@app.route('/api/admin/approve-payment/<int:payment_id>', methods=['POST'])
def approve_payment(payment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get the payment details
        cur.execute("SELECT * FROM pending_payments WHERE id = %s", (payment_id,))
        payment = cur.fetchone()
        
        if not payment:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Payment not found'})
        
        # Update payment status to completed
        cur.execute("UPDATE pending_payments SET status = 'completed' WHERE id = %s", (payment_id,))
        
        # Create a game token for the user
        cur.execute("""
            INSERT INTO game_tokens (user_email, reward, amount, used) 
            VALUES (%s, %s, %s, false)
        """, (payment['user_email'], payment['reward'], payment['amount']))
        
        conn.commit()
        print(f"✅ Payment approved. Game token created for {payment['user_email']} - Reward: {payment['reward']}")
        
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve payment error: {e}")
        return jsonify({'success': False, 'error': str(e)})

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

# ============================================
# WIN ROUTES
# ============================================

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

# Initialize tables
init_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)