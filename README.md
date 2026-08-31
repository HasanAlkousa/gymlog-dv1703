# GymLog - Training Tracker System

Final project for **DV1703**, Blekinge Institute of Technology.

GymLog is a web application for logging strength training. A user records
every set (weight x reps), and the database turns that raw log into
progression curves, personal records, muscle-group balance and program
adherence.

Everything that could be called "intelligence" in the app lives in the
database: personal records are maintained by triggers, session volume is a
derived column kept in sync by triggers, and the estimated one-rep max is a
stored function. **No ORM is used** - every statement is hand-written SQL in
`queries.py` or a stored procedure call.

## Requirements

* MySQL 8.0+ or MariaDB 10.5+
* Python 3.10+

## Setup

```bash
# 1. Create the database, the routines and the exercise catalogue
mysql -u root -p < sql/01_schema.sql
mysql -u root -p < sql/02_routines.sql
mysql -u root -p < sql/03_seed_static.sql

# 2. Install the Python dependencies
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Tell the app how to reach the database
export GYMLOG_DB_USER=root
export GYMLOG_DB_PASSWORD=yourpassword

# 4. Generate 20 weeks of training history for six users
python seed_data.py

# 5. Run it
python app.py          # http://127.0.0.1:5000
```

Log in with any of `hasan`, `meja`, `yaman`, `jamil`, `baraa`, `elin` -
password `password123`.

Alternatively, restore everything (schema, routines, triggers and data) from
the dump in one step:

```bash
mysql -u root -p < sql/gymlog_dump.sql
```

## Configuration

Read from the environment, with defaults in `db.py`:

| Variable | Default |
| --- | --- |
| `GYMLOG_DB_HOST` | `127.0.0.1` |
| `GYMLOG_DB_PORT` | `3306` |
| `GYMLOG_DB_USER` | `root` |
| `GYMLOG_DB_PASSWORD` | *(empty)* |
| `GYMLOG_DB_NAME` | `gymlog` |
| `GYMLOG_SECRET` | `dev-secret-change-me` |

## Layout

| Path | What it holds |
| --- | --- |
| `sql/01_schema.sql` | Tables, constraints, indexes, one view |
| `sql/02_routines.sql` | 2 functions, 3 procedures, 4 triggers |
| `sql/03_seed_static.sql` | Muscle groups and the exercise catalogue |
| `sql/gymlog_dump.sql` | Full dump including data |
| `queries.py` | Every SQL statement the app runs, Q1-Q6 included |
| `db.py` | Connection pool and cursor helpers |
| `app.py` | Flask routes |
| `seed_data.py` | Generates realistic training history |
| `templates/`, `static/` | Interface |
