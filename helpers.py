from functools import wraps
from flask import abort, jsonify, request
from flask_login import current_user
from models import db, StockMovement, User

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                abort(401)
            if not current_user.role.has_permission(permission):
                if request.is_json:
                    return jsonify({'error': 'Permission denied'}), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_stock_movement(asset_id, quantity, movement_type, reference_id=None):
    movement = StockMovement(
        asset_id=asset_id,
        quantity=quantity,
        movement_type=movement_type,
        reference_id=reference_id
    )
    db.session.add(movement)
    return movement

def api_response(data=None, message=None, status=200):
    payload = {}
    if data is not None:
        payload['data'] = data
    if message:
        payload['message'] = message
    return jsonify(payload), status

def api_error(message, status=400):
    return jsonify({'error': message}), status