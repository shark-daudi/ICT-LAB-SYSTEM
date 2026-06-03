import bcrypt
import json
from app import app, db
from models import Role, User

def init():
    with app.app_context():
        db.drop_all()
        db.create_all()
        roles_data = {
            'Admin': [
                'can_checkout', 'can_checkin', 'can_manage_assets', 'can_manage_users',
                'can_view_reports', 'can_be_handout_staff', 'can_be_receive_staff', 'can_be_recipient'
            ],
            'Lab Staff': [
                'can_checkout', 'can_checkin', 'can_manage_assets', 'can_view_reports',
                'can_be_handout_staff', 'can_be_receive_staff'
            ],
            'Requester': ['can_be_recipient']
        }
        roles = {}
        for name, perms in roles_data.items():
            r = Role(name=name, permissions=json.dumps(perms))
            db.session.add(r)
            roles[name] = r
        db.session.commit()

        # Admin user
        admin_hash = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
        admin = User(username='admin', email='admin@lab.com', password_hash=admin_hash, role_id=roles['Admin'].id)
        db.session.add(admin)

        # Sample requester users (teachers, students, staff, guest)
        sample_users = [
            ('teacher1', 'teacher@school.edu', 'teacher', 'Teacher'),
            ('student1', 'student@school.edu', 'student', 'Student'),
            ('staff1', 'staff@school.edu', 'non_teaching_staff', 'Non-teaching Staff'),
            ('guest1', 'guest@school.edu', 'guest', 'Guest')
        ]
        for username, email, category, _ in sample_users:
            hash_pw = bcrypt.hashpw('password123'.encode(), bcrypt.gensalt()).decode()
            u = User(username=username, email=email, password_hash=hash_pw, role_id=roles['Requester'].id, category=category)
            db.session.add(u)

        db.session.commit()
        print("Database initialised with default roles, admin (admin/admin123), and sample requesters.")

if __name__ == '__main__':
    init()