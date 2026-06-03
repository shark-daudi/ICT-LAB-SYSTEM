import logging
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime, date

import bcrypt
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask import session
from flask_limiter.util import get_remote_address

from config import Config
from models import db, Role, User, Asset, Assignment, StockMovement
from helpers import permission_required, log_stock_movement, api_error, api_response

# App setup
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

limiter = Limiter(get_remote_address, app=app, default_limits=["200 per minute"], storage_uri="memory://")

# Logging
if not app.debug:
    handler = RotatingFileHandler('ict_lab.log', maxBytes=1_000_000, backupCount=5)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    app.logger.addHandler(handler)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def start_timer():
    g.start = time.time()

@app.after_request
def add_response_time(response):
    if hasattr(g, 'start'):
        response.headers['X-Response-Time'] = f'{(time.time() - g.start) * 1000:.2f}ms'
    return response

# Error handlers
@app.errorhandler(400)
def bad_request(e):
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Bad request'}), 400
    flash('Bad request.', 'danger')
    return redirect(url_for('dashboard'))

@app.errorhandler(403)
def forbidden(e):
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Permission denied'}), 403
    flash('Permission denied.', 'danger')
    return redirect(url_for('dashboard'))

@app.errorhandler(404)
def not_found(e):
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    flash('Page not found.', 'danger')
    return redirect(url_for('dashboard'))

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f'Server Error: {e}', exc_info=True)
    db.session.rollback()
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    flash('An internal error occurred.', 'danger')
    return redirect(url_for('dashboard'))

# ---------- HTML routes ----------
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role and 'can_view_reports' in current_user.role.get_permissions():
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('my_assets'))
    return redirect(url_for('login'))

@app.route('/send-test-email')
def send_test_email():
    msg = Message('Hello from Flask!',
                  recipients=['test@example.com']) # Recipient email can be fake
    msg.body = 'This is a test email sent via Mailtrap!'
    mail.send(msg)
    return 'Test email sent! Check your Mailtrap inbox.'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            login_user(user, remember=True)
            # Clear any previous flash messages
            session.pop('_flashes', None)
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
@permission_required('can_view_reports')
def dashboard():
    return render_template('dashboard.html')

@app.route('/my-assets')
@login_required
def my_assets():
    if current_user.role and 'can_view_reports' in current_user.role.get_permissions():
        return redirect(url_for('dashboard'))
    assignments = Assignment.query.filter_by(received_by_id=current_user.id, status='out')\
        .options(db.joinedload(Assignment.asset)).order_by(Assignment.checked_out_at.desc()).all()
    return render_template('my_assets.html', assignments=assignments)

@app.route('/checkout')
@login_required
@permission_required('can_checkout')
def checkout_page():
    staff = [u for u in User.query.all() if u.role and u.role.has_permission('can_be_handout_staff')]
    requesters = User.query.join(Role).filter(Role.name == 'Requester').all()
    groups = {}
    for u in requesters:
        cat = u.category or 'Other'
        groups.setdefault(cat, []).append({'id': u.id, 'username': u.username})
    return render_template('checkout.html', staff=staff, groups=groups)

@app.route('/checkin')
@login_required
@permission_required('can_checkin')
def checkin_page():
    staff = [u for u in User.query.all() if u.role and u.role.has_permission('can_be_handout_staff')]
    all_users = User.query.order_by(User.username).all()
    return render_template('checkin.html', staff=staff, all_users=all_users)

@app.route('/assets')
@login_required
@permission_required('can_view_reports')
def assets_page():
    return render_template('assets.html')

@app.route('/reports')
@login_required
@permission_required('can_view_reports')
def reports_page():
    return render_template('reports.html')

@app.route('/admin/users')
@login_required
@permission_required('can_manage_users')
def admin_users_page():
    roles = Role.query.all()
    return render_template('admin_users.html', roles=roles)

# ---------- API routes ----------
@app.route('/api/ping')
def ping():
    return jsonify({'status': 'ok', 'time': datetime.utcnow().isoformat()})

@app.route('/api/current-user')
@login_required
def current_user_api():
    return jsonify(current_user.to_dict())

@app.route('/api/dashboard-stats')
@login_required
@permission_required('can_view_reports')
def dashboard_stats():
    total_assets = Asset.query.count()
    checked_out = Assignment.query.filter_by(status='out').count()
    overdue = Assignment.query.filter(
        Assignment.status == 'out',
        Assignment.expected_return < date.today()
    ).count()
    low_stock_assets = Asset.query.filter(
        Asset.current_stock <= Asset.reorder_level
    ).all()
    
    # Last 5 checkouts (any status)
    recent_checkouts = (
        Assignment.query
        .options(db.joinedload(Assignment.asset), db.joinedload(Assignment.received_by))
        .order_by(Assignment.checked_out_at.desc())
        .limit(5)
        .all()
    )
    
    # Last 5 checkins (returned items)
    recent_checkins = (
        Assignment.query
        .options(db.joinedload(Assignment.asset), db.joinedload(Assignment.received_by))
        .filter(Assignment.status == 'returned', Assignment.checked_in_at.isnot(None))
        .order_by(Assignment.checked_in_at.desc())
        .limit(5)
        .all()
    )
    
    return jsonify({
        'total_assets': total_assets,
        'checked_out': checked_out,
        'overdue': overdue,
        'low_stock_count': len(low_stock_assets),
        'low_stock_assets': [a.to_dict() for a in low_stock_assets],
        'recent_checkouts': [
            {
                'asset_name': a.asset.name,
                'borrower': a.received_by.username,
                'checkout_date': a.checked_out_at.strftime('%Y-%m-%d %H:%M'),
                'status': a.status
            } for a in recent_checkouts
        ],
        'recent_checkins': [
            {
                'asset_name': a.asset.name,
                'returned_by': a.returned_by.username if a.returned_by else 'Unknown',
                'checkin_date': a.checked_in_at.strftime('%Y-%m-%d %H:%M') if a.checked_in_at else '',
                'status': a.status
            } for a in recent_checkins
        ]
    })

# Assets API
@app.route('/api/assets', methods=['GET'])
@login_required
@permission_required('can_view_reports')
def get_assets():
    q = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    filter_val = request.args.get('filter', '')
    query = Asset.query
    if q:
        query = query.filter(db.or_(Asset.serial_number.ilike(f'%{q}%'), Asset.name.ilike(f'%{q}%')))
    if filter_val == 'lowstock':
        query = query.filter(Asset.current_stock <= Asset.reorder_level)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [a.to_dict() for a in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    })

@app.route('/api/assets/search')
@login_required
def search_assets():
    q = request.args.get('q', '').strip()
    results = Asset.query.filter(db.or_(Asset.serial_number.ilike(f'%{q}%'), Asset.name.ilike(f'%{q}%'))).limit(10).all()
    return jsonify([{'id': a.id, 'serial': a.serial_number, 'name': a.name} for a in results])

@app.route('/api/assets', methods=['POST'])
@login_required
@permission_required('can_manage_assets')
def create_asset():
    data = request.get_json()
    if Asset.query.filter_by(serial_number=data.get('serial_number')).first():
        return api_error('Serial number already exists')
    asset = Asset(
        serial_number=data['serial_number'],
        name=data['name'],
        model=data.get('model'),
        purchase_date=datetime.strptime(data['purchase_date'], '%Y-%m-%d').date() if data.get('purchase_date') else None,
        warranty_end=datetime.strptime(data['warranty_end'], '%Y-%m-%d').date() if data.get('warranty_end') else None,
        current_stock=int(data.get('current_stock', 1)),
        reorder_level=int(data.get('reorder_level', 0)),
        location=data.get('location')
    )
    db.session.add(asset)
    db.session.commit()
    return api_response({'id': asset.id}, 'Asset created', 201)

@app.route('/api/assets/<int:asset_id>', methods=['PUT'])
@login_required
@permission_required('can_manage_assets')
def update_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    data = request.get_json()
    if data.get('serial_number') and data['serial_number'] != asset.serial_number:
        if Asset.query.filter_by(serial_number=data['serial_number']).first():
            return api_error('Serial number already exists')
        asset.serial_number = data['serial_number']
    asset.name = data.get('name', asset.name)
    asset.model = data.get('model', asset.model)
    if data.get('purchase_date'):
        asset.purchase_date = datetime.strptime(data['purchase_date'], '%Y-%m-%d').date()
    if data.get('warranty_end'):
        asset.warranty_end = datetime.strptime(data['warranty_end'], '%Y-%m-%d').date()
    asset.reorder_level = int(data.get('reorder_level', asset.reorder_level))
    asset.location = data.get('location', asset.location)
    db.session.commit()
    return api_response(asset.to_dict(), 'Asset updated')

@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
@login_required
@permission_required('can_manage_assets')
def delete_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    if Assignment.query.filter_by(asset_id=asset_id).first():
        return api_error('Cannot delete asset with existing assignments', 400)
    db.session.delete(asset)
    db.session.commit()
    return api_response(message='Asset deleted')

@app.route('/api/assets/<int:asset_id>/stock', methods=['POST'])
@login_required
@permission_required('can_manage_assets')
def adjust_stock(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    data = request.get_json()
    qty = int(data.get('quantity', 0))
    reason = data.get('reason', 'adjustment')
    asset.current_stock += qty
    if asset.current_stock < 0:
        return api_error('Stock cannot be negative')
    log_stock_movement(asset_id, qty, reason)
    db.session.commit()
    return api_response({'current_stock': asset.current_stock}, 'Stock adjusted')

# Users API
@app.route('/api/requesters')
@login_required
def get_requesters():
    role = Role.query.filter_by(name='Requester').first()
    if not role:
        return jsonify([])
    users = User.query.filter_by(role_id=role.id).order_by(User.username).all()
    return jsonify([u.to_dict() for u in users])

@app.route('/api/staff')
@login_required
def get_staff():
    all_users = User.query.all()
    staff = [u for u in all_users if u.role and u.role.has_permission('can_be_handout_staff')]
    return jsonify([{'id': u.id, 'username': u.username, 'role': u.role.name} for u in staff])

@app.route('/api/users', methods=['GET'])
@login_required
@permission_required('can_manage_users')
def get_users():
    users = User.query.order_by(User.username).all()
    return jsonify([u.to_dict() for u in users])

@app.route('/api/users', methods=['POST'])
@login_required
@permission_required('can_manage_users')
def create_user():
    data = request.get_json()
    if User.query.filter_by(username=data.get('username')).first():
        return api_error('Username already exists')
    if User.query.filter_by(email=data.get('email')).first():
        return api_error('Email already exists')
    role = Role.query.filter_by(name=data.get('role_name')).first()
    if not role:
        return api_error('Role not found')
    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=hashed,
        role_id=role.id,
        category=data.get('category') if role.name == 'Requester' else None
    )
    db.session.add(user)
    db.session.commit()
    return api_response({'id': user.id}, 'User created', 201)

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@permission_required('can_manage_users')
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    if 'role_name' in data:
        role = Role.query.filter_by(name=data['role_name']).first()
        if not role:
            return api_error('Role not found')
        user.role_id = role.id
        user.category = data.get('category') if role.name == 'Requester' else None
    if 'password' in data and data['password']:
        user.password_hash = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    if 'email' in data:
        user.email = data['email']
    db.session.commit()
    return api_response(user.to_dict(), 'User updated')

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@permission_required('can_manage_users')
def delete_user(user_id):
    if user_id == current_user.id:
        return api_error('Cannot delete your own account')
    user = User.query.get_or_404(user_id)
    if Assignment.query.filter_by(received_by_id=user_id, status='out').count():
        return api_error('User has active assignments')
    db.session.delete(user)
    db.session.commit()
    return api_response(message='User deleted')

@app.route('/api/roles')
@login_required
def get_roles():
    return jsonify([r.to_dict() for r in Role.query.all()])

# Checkout/Checkin APIs
@app.route('/api/checkout', methods=['POST'])
@login_required
@permission_required('can_checkout')
def checkout():
    data = request.get_json()
    serial = data.get('asset_serial', '').strip()
    asset = Asset.query.filter_by(serial_number=serial).first()
    if not asset:
        return api_error('Asset not found', 404)
    if asset.current_stock <= 0:
        return api_error('Asset out of stock')
    if asset.current_stock == 1 and Assignment.query.filter_by(asset_id=asset.id, status='out').first():
        return api_error('This asset is already checked out')

    handed_out_by = User.query.get(data.get('handed_out_by_id'))
    received_by = User.query.get(data.get('received_by_id'))
    if not received_by or not received_by.role or received_by.role.name != 'Requester':
        return api_error('Receiver must be a Requester')

    due_date = None
    if data.get('due_date'):
        try:
            due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        except ValueError:
            return api_error('Invalid due date format')

    try:
        Asset.query.filter(Asset.id == asset.id, Asset.current_stock > 0).update({Asset.current_stock: Asset.current_stock - 1})
        assignment = Assignment(
            asset_id=asset.id,
            handed_out_by_id=handed_out_by.id if handed_out_by else current_user.id,
            received_by_id=received_by.id,
            receiver_category=received_by.category,
            system_checkout_by_id=current_user.id,
            expected_return=due_date,
            purpose=data.get('purpose', ''),
            status='out'
        )
        db.session.add(assignment)
        db.session.flush()
        log_stock_movement(asset.id, -1, 'checkout', assignment.id)
        db.session.commit()
        return api_response({'assignment_id': assignment.id}, 'Checkout successful', 201)
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Checkout error: {e}')
        return api_error('Checkout failed', 500)

@app.route('/api/asset/active')
@login_required
def get_active_assignment():
    serial = request.args.get('serial', '').strip()
    asset = Asset.query.filter_by(serial_number=serial).first()
    if not asset:
        return api_error('Asset not found', 404)
    assignment = Assignment.query.filter_by(asset_id=asset.id, status='out').first()
    if not assignment:
        return api_error('No active assignment for this asset', 404)
    return jsonify({
        'assignment_id': assignment.id,
        'asset_name': asset.name,
        'serial': asset.serial_number,
        'received_by_name': assignment.received_by.username,
        'received_by_id': assignment.received_by_id,
        'checked_out_at': assignment.checked_out_at.strftime('%Y-%m-%d %H:%M'),
        'purpose': assignment.purpose,
        'expected_return': assignment.expected_return.isoformat() if assignment.expected_return else None
    })

@app.route('/api/checkin', methods=['POST'])
@login_required
@permission_required('can_checkin')
def checkin():
    data = request.get_json()
    assignment = Assignment.query.filter_by(id=data.get('assignment_id'), status='out').first()
    if not assignment:
        return api_error('Assignment not found or already returned', 404)
    try:
        assignment.returned_by_id = data.get('returned_by_id')
        assignment.received_back_by_id = data.get('received_back_by_id')
        assignment.system_checked_in_by_id = current_user.id
        assignment.checked_in_at = datetime.utcnow()
        assignment.return_purpose = data.get('return_purpose', '')
        assignment.status = 'returned'
        Asset.query.filter_by(id=assignment.asset_id).update({Asset.current_stock: Asset.current_stock + 1})
        log_stock_movement(assignment.asset_id, 1, 'checkin', assignment.id)
        db.session.commit()
        return api_response(message='Checkin successful')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Checkin error: {e}')
        return api_error('Checkin failed', 500)

# Reports API
@app.route('/api/reports/active')
@login_required
@permission_required('can_view_reports')
def reports_active():
    assignments = Assignment.query.options(db.joinedload(Assignment.asset), db.joinedload(Assignment.received_by))\
        .filter_by(status='out').order_by(Assignment.checked_out_at.desc()).all()
    return jsonify([a.to_dict() for a in assignments])

@app.route('/api/reports/overdue')
@login_required
@permission_required('can_view_reports')
def reports_overdue():
    today = date.today()
    assignments = Assignment.query.options(db.joinedload(Assignment.asset), db.joinedload(Assignment.received_by))\
        .filter(Assignment.status == 'out', Assignment.expected_return < today).order_by(Assignment.expected_return).all()
    result = []
    for a in assignments:
        d = a.to_dict()
        if a.expected_return:
            d['days_overdue'] = (today - a.expected_return).days
        result.append(d)
    return jsonify(result)

@app.route('/api/reports/history')
@login_required
@permission_required('can_view_reports')
def reports_history():
    asset_id = request.args.get('asset_id')
    user_id = request.args.get('user_id')
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    query = Assignment.query.options(db.joinedload(Assignment.asset), db.joinedload(Assignment.received_by))
    if asset_id:
        query = query.filter_by(asset_id=asset_id)
    if user_id:
        query = query.filter_by(received_by_id=user_id)
    if category:
        query = query.filter_by(receiver_category=category)
    if start_date:
        query = query.filter(Assignment.checked_out_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Assignment.checked_out_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    pagination = query.order_by(Assignment.checked_out_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [a.to_dict() for a in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)