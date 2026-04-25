from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============ IN-MEMORY STORAGE (NO DATABASE NEEDED) ============
# This stores users even when the database is down

users = []
pending_funding = []
pending_purchases = []
pending_referrals = []

# Add test user so regular users can login
users.append({
    'id': 1,
    'name': 'Test User',
    'email': 'test@test.com',
    'phone': '08012345678',
    'password': '123456',
    'referral_code': 'TEST1234',
    'referral_count': 0,
    'wallet_balance': 1000,
    'referral_reward_claimed': False
})

# Add a demo user
users.append({
    'id': 2,
    'name': 'Demo User',
    'email': 'demo@onslot.com',
    'phone': '08012345679',
    'password': 'demo123',
    'referral_code': 'DEMO5678',
    'referral_count': 0,
    'wallet_balance': 500,
    'referral_reward_claimed': False
})

print(f"✅ Loaded {len(users)} users into memory")

# ============ ROUTES ============

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'ok', 'message': 'OnSlot API is running!', 'users_loaded': len(users)})

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok', 
        'message': 'API is healthy', 
        'users_loaded': len(users),
        'mode': 'in-memory'
    })

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
        
        # Check if email exists
        if any(u['email'] == email for u in users):
            return jsonify({'success': False, 'error': 'Email already registered'})
        
        # Generate referral code
        referral_code = name[:3].upper() + str(random.randint(1000, 9999))
        
        # Create new user
        new_user = {
            'id': len(users) + 1,
            'name': name,
            'email': email,
            'phone': phone,
            'password': password,
            'referral_code': referral_code,
            'referral_count': 0,
            'wallet_balance': 0,
            'referral_reward_claimed': False
        }
        users.append(new_user)
        
        # Handle referral
        if referral_code_input:
            for u in users:
                if u['referral_code'] == referral_code_input:
                    u['referral_count'] = u.get('referral_count', 0) + 1
                    break
        
        print(f"✅ New user created: {email}")
        return jsonify({'success': True, 'user': new_user})
        
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        print(f"Login attempt: {email}")
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'})
        
        # Admin login (hardcoded - always works)
        if email == "admin" and password == "admin123":
            print("✅ Admin login successful")
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
        
        # Regular user login - search in memory
        for user in users:
            if user['email'] == email and user['password'] == password:
                print(f"✅ User login successful: {email}")
                # Don't send password back
                user_copy = user.copy()
                user_copy.pop('password', None)
                return jsonify({'success': True, 'user': user_copy})
        
        print(f"❌ Login failed: {email}")
        return jsonify({'success': False, 'error': 'Invalid credentials'})
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/<email>', methods=['GET'])
def get_user(email):
    for user in users:
        if user['email'] == email:
            user_copy = user.copy()
            user_copy.pop('password', None)
            return jsonify(user_copy)
    return jsonify(None)

# ============ WALLET FUNDING ============

@app.route('/api/submit-funding', methods=['POST'])
def submit_funding():
    try:
        data = request.json
        print(f"💰 Funding request: {data}")
        
        user_email = data.get('userEmail')
        user_name = data.get('userName')
        user_phone = data.get('userPhone')
        bank_name = data.get('bankName') or data.get('account_name') or 'N/A'
        amount_to_add = data.get('amount')
        service_charge = data.get('serviceCharge', 50)
        total_amount = data.get('totalAmount', amount_to_add)
        transaction_ref = data.get('transactionRef')
        payment_method = data.get('paymentMethod')
        
        if not user_email:
            return jsonify({'success': False, 'error': 'User email required'})
        if not amount_to_add or amount_to_add <= 0:
            return jsonify({'success': False, 'error': 'Valid amount required'})
        
        new_funding = {
            'id': len(pending_funding) + 1,
            'user_email': user_email,
            'user_name': user_name,
            'user_phone': user_phone,
            'bank_name': bank_name,
            'amount': amount_to_add,
            'service_charge': service_charge,
            'total_amount': total_amount,
            'transaction_ref': transaction_ref,
            'payment_method': payment_method,
            'status': 'pending',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        pending_funding.append(new_funding)
        
        print(f"✅ Funding request created with ID: {new_funding['id']}")
        return jsonify({'success': True, 'payment_id': new_funding['id']})
        
    except Exception as e:
        print(f"Submit funding error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/pending-funding', methods=['GET'])
def get_pending_funding():
    return jsonify([f for f in pending_funding if f['status'] == 'pending'])

@app.route('/api/admin/approve-funding/<int:payment_id>', methods=['POST'])
def approve_funding(payment_id):
    for funding in pending_funding:
        if funding['id'] == payment_id:
            funding['status'] = 'completed'
            # Add to user wallet
            for user in users:
                if user['email'] == funding['user_email']:
                    user['wallet_balance'] = user.get('wallet_balance', 0) + funding['amount']
                    print(f"✅ Added ₦{funding['amount']} to {user['email']}. New balance: ₦{user['wallet_balance']}")
                    break
            break
    return jsonify({'success': True})

@app.route('/api/admin/decline-funding/<int:payment_id>', methods=['POST'])
def decline_funding(payment_id):
    for funding in pending_funding:
        if funding['id'] == payment_id:
            funding['status'] = 'declined'
            break
    return jsonify({'success': True})

# ============ DATA PURCHASE ============

@app.route('/api/submit-purchase', methods=['POST'])
def submit_purchase():
    try:
        data = request.json
        print(f"📱 Purchase request: {data}")
        
        user_email = data.get('userEmail')
        plan_price = data.get('planPrice', 0)
        service_charge = data.get('serviceCharge', 50)
        total_amount = plan_price + service_charge
        
        # Find user and deduct balance
        user_found = None
        for user in users:
            if user['email'] == user_email:
                user_found = user
                if user.get('wallet_balance', 0) < total_amount:
                    return jsonify({'success': False, 'error': f'Insufficient balance. Need ₦{total_amount}'})
                user['wallet_balance'] = user.get('wallet_balance', 0) - total_amount
                print(f"💰 Deducted ₦{total_amount} from {user_email}. New balance: ₦{user['wallet_balance']}")
                break
        
        if not user_found:
            return jsonify({'success': False, 'error': 'User not found'})
        
        new_purchase = {
            'id': len(pending_purchases) + 1,
            'user_email': user_email,
            'user_name': data.get('userName'),
            'user_phone': data.get('userPhone'),
            'network': data.get('network'),
            'plan_size': data.get('planSize'),
            'plan_price': plan_price,
            'service_charge': service_charge,
            'total_amount': total_amount,
            'phone_number': data.get('phoneNumber'),
            'validity': data.get('validity'),
            'status': 'pending',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        pending_purchases.append(new_purchase)
        
        print(f"✅ Purchase request created with ID: {new_purchase['id']}")
        return jsonify({'success': True, 'purchase_id': new_purchase['id']})
        
    except Exception as e:
        print(f"Submit purchase error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/pending-purchases', methods=['GET'])
def get_pending_purchases():
    return jsonify([p for p in pending_purchases if p['status'] == 'pending'])

@app.route('/api/admin/approve-purchase/<int:purchase_id>', methods=['POST'])
def approve_purchase(purchase_id):
    for purchase in pending_purchases:
        if purchase['id'] == purchase_id:
            purchase['status'] = 'completed'
            print(f"✅ Purchase {purchase_id} approved - Data sent to {purchase['phone_number']}")
            break
    return jsonify({'success': True})

@app.route('/api/admin/decline-purchase/<int:purchase_id>', methods=['POST'])
def decline_purchase(purchase_id):
    for purchase in pending_purchases:
        if purchase['id'] == purchase_id:
            purchase['status'] = 'declined'
            # Refund user
            for user in users:
                if user['email'] == purchase['user_email']:
                    user['wallet_balance'] = user.get('wallet_balance', 0) + purchase['total_amount']
                    print(f"💰 Refunded ₦{purchase['total_amount']} to {user['email']}")
                    break
            break
    return jsonify({'success': True})

# ============ REFERRAL REWARDS ============

@app.route('/api/submit-referral-reward', methods=['POST'])
def submit_referral_reward():
    try:
        data = request.json
        new_referral = {
            'id': len(pending_referrals) + 1,
            'user_email': data.get('userEmail'),
            'user_name': data.get('userName'),
            'phone': data.get('phone'),
            'network': data.get('network'),
            'amount': data.get('amount', 400),
            'status': 'pending',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        pending_referrals.append(new_referral)
        return jsonify({'success': True, 'referral_id': new_referral['id']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/pending-referrals', methods=['GET'])
def get_pending_referrals():
    return jsonify([r for r in pending_referrals if r['status'] == 'pending'])

@app.route('/api/admin/approve-referral/<int:referral_id>', methods=['POST'])
def approve_referral(referral_id):
    for referral in pending_referrals:
        if referral['id'] == referral_id:
            referral['status'] = 'completed'
            for user in users:
                if user['email'] == referral['user_email']:
                    user['wallet_balance'] = user.get('wallet_balance', 0) + 400
                    user['referral_reward_claimed'] = True
                    break
            break
    return jsonify({'success': True})

@app.route('/api/admin/decline-referral/<int:referral_id>', methods=['POST'])
def decline_referral(referral_id):
    for referral in pending_referrals:
        if referral['id'] == referral_id:
            referral['status'] = 'declined'
            break
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting server on port {port}")
    print(f"📝 Test users loaded:")
    print(f"   - test@test.com / 123456 (Wallet: ₦1000)")
    print(f"   - demo@onslot.com / demo123 (Wallet: ₦500)")
    print(f"   - admin / admin123 (Admin access)")
    app.run(host='0.0.0.0', port=port)