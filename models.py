from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    permissions = db.Column(db.Text)  # JSON string

    def get_permissions(self):
        return json.loads(self.permissions) if self.permissions else []

    def has_permission(self, perm):
        return perm in self.get_permissions()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'permissions': self.get_permissions()
        }

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    category = db.Column(db.String(50))  # teacher, student, non_teaching_staff, guest
    role = db.relationship('Role', backref='users')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role.name if self.role else None,
            'category': self.category
        }

class Asset(db.Model):
    __tablename__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    model = db.Column(db.String(100))
    purchase_date = db.Column(db.Date)
    warranty_end = db.Column(db.Date)
    current_stock = db.Column(db.Integer, default=1)
    reorder_level = db.Column(db.Integer, default=0)
    location = db.Column(db.String(200))

    def to_dict(self):
        return {
            'id': self.id,
            'serial_number': self.serial_number,
            'name': self.name,
            'model': self.model,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'warranty_end': self.warranty_end.isoformat() if self.warranty_end else None,
            'current_stock': self.current_stock,
            'reorder_level': self.reorder_level,
            'location': self.location
        }

class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    handed_out_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    received_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_category = db.Column(db.String(50))  # denormalised
    system_checkout_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    checked_out_at = db.Column(db.DateTime, default=datetime.utcnow)
    expected_return = db.Column(db.Date)
    purpose = db.Column(db.Text, nullable=False)
    returned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    received_back_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    system_checked_in_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    checked_in_at = db.Column(db.DateTime, nullable=True)
    return_purpose = db.Column(db.Text)
    status = db.Column(db.String(20), default='out')  # out, returned

    asset = db.relationship('Asset', backref='assignments')
    handed_out_by = db.relationship('User', foreign_keys=[handed_out_by_id])
    received_by = db.relationship('User', foreign_keys=[received_by_id])
    system_checkout_by = db.relationship('User', foreign_keys=[system_checkout_by_id])
    returned_by = db.relationship('User', foreign_keys=[returned_by_id])
    received_back_by = db.relationship('User', foreign_keys=[received_back_by_id])
    system_checked_in_by = db.relationship('User', foreign_keys=[system_checked_in_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'asset_name': self.asset.name if self.asset else None,
            'serial': self.asset.serial_number if self.asset else None,
            'borrower': self.received_by.username if self.received_by else None,
            'category': self.receiver_category,
            'checkout_date': self.checked_out_at.strftime('%Y-%m-%d %H:%M') if self.checked_out_at else None,
            'due_date': self.expected_return.isoformat() if self.expected_return else None,
            'purpose': self.purpose,
            'status': self.status,
            'checked_in': self.checked_in_at.strftime('%Y-%m-%d %H:%M') if self.checked_in_at else None
        }

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    movement_type = db.Column(db.String(50))
    reference_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
