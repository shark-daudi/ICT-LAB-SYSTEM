# ICT Lab Asset Management System

Flask-based asset management system for ICT labs — checkout, checkin, reporting, and user administration.

## Quick Start

```bash
pip install -r requirements.txt
python init_db.py        # creates DB + sample data
python app.py            # starts on http://localhost:5000
```

Default admin: **admin / admin123**

## Project Structure

```
ict_lab/
├── app.py               # Main Flask app + all routes
├── models.py            # SQLAlchemy models
├── helpers.py           # Permission decorator, stock logging
├── config.py            # Configuration (env vars)
├── init_db.py           # DB init + seed script
├── requirements.txt
├── static/
│   ├── css/custom.css
│   └── js/
│       ├── api.js           # Fetch wrapper
│       ├── autocomplete.js  # Datalist helper
│       ├── theme-switcher.js
│       └── toast.js
└── templates/
    ├── layout.html
    ├── _sidebar_nav.html
    ├── login.html
    ├── dashboard.html
    ├── checkout.html
    ├── checkin.html
    ├── assets.html
    ├── reports.html
    └── admin_users.html
```

## Roles & Permissions

| Permission            | Admin | Lab Staff | Requester |
|-----------------------|-------|-----------|-----------|
| can_checkout          | ✓     | ✓         |           |
| can_checkin           | ✓     | ✓         |           |
| can_manage_assets     | ✓     | ✓         |           |
| can_view_reports      | ✓     | ✓         |           |
| can_manage_users      | ✓     |           |           |
| can_be_handout_staff  | ✓     | ✓         |           |

## API Endpoints

| Method | Endpoint                   | Description                  |
|--------|----------------------------|------------------------------|
| GET    | /api/dashboard-stats       | Dashboard summary data       |
| GET    | /api/assets                | List assets (search, page)   |
| GET    | /api/assets/search         | Autocomplete asset search    |
| POST   | /api/assets                | Create asset                 |
| PUT    | /api/assets/<id>           | Update asset                 |
| DELETE | /api/assets/<id>           | Delete asset                 |
| POST   | /api/assets/<id>/stock     | Adjust stock                 |
| POST   | /api/checkout              | Checkout asset               |
| GET    | /api/asset/active          | Active assignment by serial  |
| POST   | /api/checkin               | Checkin asset                |
| GET    | /api/reports/active        | Active loans report          |
| GET    | /api/reports/overdue       | Overdue report               |
| GET    | /api/reports/history       | Assignment history           |
| GET    | /api/users                 | List users (admin)           |
| POST   | /api/users                 | Create user (admin)          |
| PUT    | /api/users/<id>            | Update user (admin)          |
| DELETE | /api/users/<id>            | Delete user (admin)          |
| GET    | /api/staff                 | Staff dropdown list          |
| GET    | /api/requesters            | Requesters grouped by cat    |
| GET    | /api/roles                 | Roles list                   |

## Production

```bash
# Use MySQL: set DATABASE_URL in .env
DATABASE_URL=mysql+pymysql://user:pass@host/dbname

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Set `SECRET_KEY` and `FLASK_ENV=production` in your environment.

## Reset Database

```bash
python init_db.py --drop   # drops all tables and re-seeds
```
