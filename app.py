from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import random
from datetime import datetime

app = Flask(__name__)

# Configure CORS properly
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')

print(f"Database URL loaded: {'Yes' if DATABASE_URL else 'No'}")

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable not set!")
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise e

# Add missing column to existing table
def add_missing_columns():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Add account_name column if it doesn't exist
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='pending_payments' AND column_name='account_name') THEN
                    ALTER TABLE pending_payments ADD COLUMN account_name VARCHAR(100);
                END IF;
            END $$;
        """)
        
        # Add amount_sent column if it doesn't exist
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='pending_payments' AND column_name='amount_sent') THEN
                    ALTER TABLE pending_payments ADD COLUMN amount_sent INT DEFAULT 0;
                END IF;
            END $$;
        """)
        
        conn.commit()
        print("✅ Missing columns added successfully!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error adding columns: {e}")

# Create tables
def create_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100) UNIQUE,
                phone VARCHAR(20),
                password VARCHAR(255),
                referral_code VARCHAR(50),
                referral_count INT DEFAULT 0,
                wallet_balance INT DEFAULT 0,
                referral_reward_claimed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create pending_payments table with account_name column
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                user_phone VARCHAR(20),
                account_name VARCHAR(100),
                amount INT,
                amount_sent INT,
                service_charge INT DEFAULT 50,
                total_amount INT,
                transaction_ref VARCHAR(100),
                payment_method VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create pending_purchases table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_purchases (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                user_phone VARCHAR(20),
                network VARCHAR(20),
                plan_size VARCHAR(50),
                plan_price INT,
                service_charge INT DEFAULT 50,
                total_amount INT,
                phone_number VARCHAR(20),
                validity VARCHAR(50),
                wallet_balance_before INT,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create pending_referrals table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_referrals (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(100),
                user_name VARCHAR(100),
                phone VARCHAR(20),
                network VARCHAR(20),
                amount INT DEFAULT 400,
                status VARCHAR(20) DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        
        conn.commit()
        print("✅ Tables created successfully!")
        
        # Insert test user if no users exist
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        if user_count == 0:
            test_referral_code = "TEST" + str(random.randint(1000, 9999))
            cur.execute("""
                INSERT INTO users (name, email, phone, password, referral_code, wallet_balance)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ("Test User", "test@test.com", "08012345678", "123456", test_referral_code, 1000))
            conn.commit()
            print("✅ Test user created (email: test@test.com, password: 123456)")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error creating tables: {e}")

# Initialize tables
create_tables()
add_missing_columns()  # Add missing columns to existing table

# ============ ROUTES ============

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'ok', 'message': 'OnSlot Data API is running'})

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({'status': 'ok', 'message': 'API is healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Database connection failed', 'error': str(e)}), 500

# ============ USER AUTHENTICATION ============

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        password = data.get('password')
        referral_code_input = data.get('referralCode')
        
        if not all([name, email, phone, password]):
            return jsonify({'success': False, 'error': 'All fields are required'})
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if user exists
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
            RETURNING id, name, email, phone, referral_code, referral_count, wallet_balance
        """, (name, email, phone, password, referral_code))
        
        user = cur.fetchone()
        
        # Handle referral
        if referral_code_input:
            cur.execute("UPDATE users SET referral_count = referral_count + 1 WHERE referral_code = %s", (referral_code_input,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'user': user})
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'})
        
        # Handle admin login
        if email == "admin" and password == "admin123":
            admin_user = {
                'id': 999,
                'name': 'Administrator',
                'email': 'admin@onslot.com',
                'phone': '00000000000',
                'referral_code': 'ADMIN',
                'referral_count': 0,
                'wallet_balance': 0,
                'isAdmin': True
            }
            return jsonify({'success': True, 'user': admin_user})
        
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
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/user/<email>', methods=['GET'])
def get_user(email):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name, email, phone, referral_code, referral_count, wallet_balance, referral_reward_claimed FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify(user) if user else jsonify(None)
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify(None), 500

# ============ WALLET FUNDING ============

@app.route('/api/submit-funding', methods=['POST'])
def submit_funding():
    try:
        data = request.json
        print(f"💰 Funding request received: {data}")
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        # Get data from request
        user_email = data.get('userEmail')
        user_name = data.get('userName')
        user_phone = data.get('userPhone')
        account_name = data.get('accountName')
        amount_to_add = data.get('amount')
        amount_sent = data.get('amountSent', amount_to_add + 50 if amount_to_add else 0)
        service_charge = data.get('serviceCharge', 50)
        total_amount = data.get('totalAmount', amount_to_add)
        transaction_ref = data.get('transactionRef')
        payment_method = data.get('paymentMethod')
        
        print(f"Processing: {account_name} sends ₦{amount_sent}, fee ₦{service_charge}, gets ₦{amount_to_add}")
        
        # Validate required fields
        if not user_email:
            return jsonify({'success': False, 'error': 'User email required'})
        if not user_name:
            return jsonify({'success': False, 'error': 'User name required'})
        if not account_name:
            return jsonify({'success': False, 'error': 'Account name required'})
        if amount_to_add is None or amount_to_add <= 0:
            return jsonify({'success': False, 'error': 'Valid amount required'})
        if not transaction_ref:
            return jsonify({'success': False, 'error': 'Transaction reference required'})
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert into pending_payments
        cur.execute("""
            INSERT INTO pending_payments (
                user_email, user_name, user_phone, account_name, amount, 
                amount_sent, service_charge, total_amount, transaction_ref, payment_method
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_email, user_name, user_phone, account_name, amount_to_add, 
              amount_sent, service_charge, total_amount, transaction_ref, payment_method))
        
        payment_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"✅ Funding request inserted with ID: {payment_id}")
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'payment_id': payment_id})
        
    except Exception as e:
        print(f"❌ Submit funding error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

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
        print(f"✅ Approving funding ID: {payment_id}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get payment details
        cur.execute("SELECT user_email, amount FROM pending_payments WHERE id = %s", (payment_id,))
        payment = cur.fetchone()
        
        if not payment:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Payment not found'})
        
        user_email = payment[0]
        amount_to_add = payment[1]
        
        print(f"Adding ₦{amount_to_add} to user {user_email}")
        
        # ADD money to user's wallet
        cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", 
                   (amount_to_add, user_email))
        
        # Update payment status
        cur.execute("UPDATE pending_payments SET status = 'completed' WHERE id = %s", (payment_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ Funding approved! ₦{amount_to_add} added to {user_email}")
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Approve funding error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/decline-funding/<int:payment_id>', methods=['POST'])
def decline_funding(payment_id):
    try:
        print(f"❌ Declining funding ID: {payment_id}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Just mark as declined - NO money action needed
        cur.execute("UPDATE pending_payments SET status = 'declined' WHERE id = %s", (payment_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        print(f"✅ Funding request {payment_id} marked as declined")
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Decline funding error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ DATA PURCHASE ============

@app.route('/api/submit-purchase', methods=['POST'])
def submit_purchase():
    try:
        data = request.json
        print(f"📱 Purchase request: {data}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get current wallet balance
        cur.execute("SELECT wallet_balance FROM users WHERE email = %s", (data.get('userEmail'),))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'})
        
        balance = result[0]
        plan_price = data.get('planPrice')
        service_charge = data.get('serviceCharge', 50)
        total_amount = plan_price + service_charge
        
        if balance < total_amount:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Insufficient balance. Need ₦{total_amount} (₦{plan_price} + ₦{service_charge} fee)'})
        
        # Deduct total amount from wallet immediately
        cur.execute("UPDATE users SET wallet_balance = wallet_balance - %s WHERE email = %s", 
                   (total_amount, data.get('userEmail')))
        
        # Insert purchase record
        cur.execute("""
            INSERT INTO pending_purchases (
                user_email, user_name, user_phone, network, plan_size, 
                plan_price, service_charge, total_amount, phone_number, 
                validity, wallet_balance_before
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('userEmail'), 
            data.get('userName'), 
            data.get('userPhone'),
            data.get('network'), 
            data.get('planSize'),
            plan_price,
            service_charge,
            total_amount,
            data.get('phoneNumber'),
            data.get('validity'),
            balance
        ))
        
        purchase_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ Purchase request created with ID: {purchase_id}")
        return jsonify({'success': True, 'purchase_id': purchase_id})
        
    except Exception as e:
        print(f"Submit purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/pending-purchases', methods=['GET'])
def get_pending_purchases():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, user_email, user_name, user_phone, network, plan_size, 
                   plan_price, service_charge, total_amount, phone_number, 
                   validity, status, timestamp 
            FROM pending_purchases 
            WHERE status = 'pending' 
            ORDER BY id DESC
        """)
        purchases = cur.fetchall()
        cur.close()
        conn.close()
        
        for purchase in purchases:
            purchase['amount'] = purchase['plan_price']
            purchase['wallet_balance'] = 'Pending'
            
        return jsonify(purchases)
    except Exception as e:
        print(f"Get pending purchases error: {e}")
        return jsonify([])

@app.route('/api/admin/approve-purchase/<int:purchase_id>', methods=['POST'])
def approve_purchase(purchase_id):
    try:
        print(f"✅ Approving purchase ID: {purchase_id}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_purchases SET status = 'completed' WHERE id = %s", (purchase_id,))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/decline-purchase/<int:purchase_id>', methods=['POST'])
def decline_purchase(purchase_id):
    try:
        print(f"❌ Declining purchase ID: {purchase_id}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get purchase details to refund
        cur.execute("SELECT user_email, total_amount FROM pending_purchases WHERE id = %s", (purchase_id,))
        purchase = cur.fetchone()
        
        if purchase:
            user_email = purchase[0]
            total_amount = purchase[1]
            
            # REFUND the user
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE email = %s", 
                       (total_amount, user_email))
            cur.execute("UPDATE pending_purchases SET status = 'declined' WHERE id = %s", (purchase_id,))
            conn.commit()
            print(f"✅ Refunded ₦{total_amount} to {user_email}")
        
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ REFERRAL REWARDS ============

@app.route('/api/submit-referral-reward', methods=['POST'])
def submit_referral_reward():
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO pending_referrals (user_email, user_name, phone, network, amount) 
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('userEmail'),
            data.get('userName'),
            data.get('phone'),
            data.get('network'),
            data.get('amount', 400)
        ))
        
        referral_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'referral_id': referral_id})
    except Exception as e:
        print(f"Submit referral reward error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/pending-referrals', methods=['GET'])
def get_pending_referrals():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pending_referrals WHERE status = 'pending' ORDER BY id DESC")
        referrals = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(referrals)
    except Exception as e:
        print(f"Get pending referrals error: {e}")
        return jsonify([])

@app.route('/api/admin/approve-referral/<int:referral_id>', methods=['POST'])
def approve_referral(referral_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT user_email FROM pending_referrals WHERE id = %s", (referral_id,))
        result = cur.fetchone()
        
        if result:
            cur.execute("UPDATE users SET wallet_balance = wallet_balance + 400, referral_reward_claimed = TRUE WHERE email = %s", (result[0],))
            cur.execute("UPDATE pending_referrals SET status = 'completed' WHERE id = %s", (referral_id,))
            conn.commit()
        
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Approve referral error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/decline-referral/<int:referral_id>', methods=['POST'])
def decline_referral(referral_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE pending_referrals SET status = 'declined' WHERE id = %s", (referral_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Decline referral error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Add OPTIONS handler for CORS preflight
@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)