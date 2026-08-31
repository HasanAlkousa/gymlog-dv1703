"""
Data generator.

Creates six users with roughly five months of training history each.
The generator models progressive overload (weights creep up, with an
occasional bad week and one deload) so that the statistics queries have
something realistic to find instead of random noise.

Run after the three SQL files:
    python seed_data.py
"""
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

import db

random.seed(1664)

WEEKS = 20
TODAY = date.today()

USERS = [
    # username, full name, gender, height, start bodyweight, strength level
    ("hasan",  "Hasan Alkousa",   "male",   181, 82.0, 1.00),
    ("meja",   "Meja Lindqvist",  "female", 168, 63.0, 0.72),
    ("yaman",  "Yaman Haddad",    "male",   176, 74.0, 0.88),
    ("jamil",  "Jamil Alkousa",   "male",   184, 90.0, 1.10),
    ("baraa",  "Baraa Nasser",    "male",   172, 70.0, 0.80),
    ("elin",   "Elin Persson",    "female", 174, 68.0, 0.78),
]

# name -> (base 5RM weight for strength level 1.0, increment per week)
LIFTS = {
    "Back Squat":             (100, 1.6),
    "Barbell Bench Press":    (75,  1.0),
    "Deadlift":               (120, 1.8),
    "Overhead Press":         (45,  0.6),
    "Barbell Row":            (65,  0.9),
    "Romanian Deadlift":      (85,  1.2),
    "Lat Pulldown":           (60,  0.8),
    "Leg Press":              (150, 2.5),
    "Incline Dumbbell Press": (26,  0.4),
    "Barbell Curl":           (30,  0.4),
    "Triceps Pushdown":       (32,  0.4),
    "Lateral Raise":          (10,  0.15),
    "Leg Curl":               (45,  0.6),
    "Hip Thrust":             (90,  1.5),
    "Face Pull":              (25,  0.3),
    "Standing Calf Raise":    (80,  1.0),
    "Cable Crunch":           (40,  0.5),
    "Pull-up":                (0,   0.0),
    "Hanging Leg Raise":      (0,   0.0),
}

PROGRAMS = {
    "Upper A": [("Barbell Bench Press", 4, 6), ("Barbell Row", 4, 8),
                ("Overhead Press", 3, 8), ("Lat Pulldown", 3, 10),
                ("Barbell Curl", 3, 12), ("Triceps Pushdown", 3, 12)],
    "Lower A": [("Back Squat", 4, 5), ("Romanian Deadlift", 3, 8),
                ("Leg Press", 3, 10), ("Leg Curl", 3, 12),
                ("Standing Calf Raise", 4, 15), ("Cable Crunch", 3, 15)],
    "Upper B": [("Incline Dumbbell Press", 4, 8), ("Pull-up", 4, 8),
                ("Lateral Raise", 4, 15), ("Face Pull", 3, 15),
                ("Barbell Curl", 3, 10)],
    "Lower B": [("Deadlift", 3, 5), ("Hip Thrust", 4, 8),
                ("Leg Press", 3, 12), ("Hanging Leg Raise", 3, 12)],
}

# Two lifts are deliberately made to stall: they progress for nine weeks
# and then drift slightly downwards. Q3 in the report is what finds them.
STALLING = {"Overhead Press", "Barbell Bench Press"}
STALL_WEEK = 9

ROTATION = ["Upper A", "Lower A", "Upper B", "Lower B"]
# Which weekday each of the four sessions normally lands on.
WEEKDAYS = [0, 1, 3, 4]  # Mon, Tue, Thu, Fri


def round_to_plate(weight, step=2.5):
    if weight <= 0:
        return 0
    return max(step, round(weight / step) * step)


def fetch_lookup():
    rows = db.query_all("SELECT exercise_id, name, equipment FROM Exercise")
    return {r["name"]: r for r in rows}


def create_users():
    ids = {}
    for username, full_name, gender, height, _bw, _lvl in USERS:
        existing = db.query_one(
            "SELECT user_id FROM Users WHERE username = %s", (username,))
        if existing:
            ids[username] = existing["user_id"]
            continue
        ids[username] = db.execute(
            """INSERT INTO Users (username, email, password_hash, full_name,
                                  birth_date, gender, height_cm)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (username, f"{username}@example.com",
             generate_password_hash("password123"), full_name,
             date(1999, 1, 1) + timedelta(days=random.randint(0, 2500)),
             gender, height))
    return ids


def create_programs(user_id, ex_lookup):
    program_ids = {}
    for name, items in PROGRAMS.items():
        pid = db.execute(
            """INSERT INTO Program (user_id, name, description, days_per_week)
               VALUES (%s, %s, %s, %s)""",
            (user_id, name, f"{name} day of a four-day upper/lower split", 4))
        for position, (ex_name, sets, reps) in enumerate(items, start=1):
            db.execute(
                """INSERT INTO ProgramExercise
                       (program_id, exercise_id, position, target_sets, target_reps)
                   VALUES (%s, %s, %s, %s, %s)""",
                (pid, ex_lookup[ex_name]["exercise_id"], position, sets, reps))
        program_ids[name] = pid
    return program_ids


def working_weight(base, increment, level, week, deload_week, stalling=False):
    """Progressive overload, with one deload week and an optional plateau."""
    if stalling and week > STALL_WEEK:
        # Peaked at STALL_WEEK, then slowly drifting backwards.
        effective_week = STALL_WEEK - 0.35 * (week - STALL_WEEK)
    else:
        effective_week = week

    weight = (base * level) + increment * effective_week
    if week == deload_week:
        weight *= 0.85
    return round_to_plate(weight * random.uniform(0.985, 1.01))


def seed_history(user_id, level, start_bodyweight, ex_lookup, program_ids):
    deload_week = WEEKS // 2
    bodyweight = start_bodyweight

    for week in range(WEEKS):
        monday = TODAY - timedelta(days=TODAY.weekday() + 7 * (WEEKS - 1 - week))

        # Weekly weigh-in, with a slow drift.
        bodyweight += random.uniform(-0.35, 0.45)
        db.execute(
            """INSERT INTO BodyMeasurement (user_id, measured_on, weight_kg, body_fat_pct)
               VALUES (%s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE weight_kg = VALUES(weight_kg)""",
            (user_id, monday, round(bodyweight, 1),
             round(random.uniform(12, 24), 1)))

        # Most weeks are four sessions, some are three (life happens).
        planned = ROTATION if random.random() > 0.22 else random.sample(ROTATION, 3)

        for idx, program_name in enumerate(planned):
            day = monday + timedelta(days=WEEKDAYS[idx % len(WEEKDAYS)])
            if day > TODAY:
                continue

            started = datetime.combine(
                day, datetime.min.time()) + timedelta(
                hours=random.choice([7, 16, 17, 18]),
                minutes=random.choice([0, 10, 20, 30]))
            duration = random.randint(52, 88)

            workout_id = db.execute(
                """INSERT INTO Workout (user_id, program_id, started_at, notes)
                   VALUES (%s, %s, %s, %s)""",
                (user_id, program_ids[program_name], started,
                 random.choice([None, None, None, "Felt strong",
                                "Short on time", "Bad sleep", "New PR attempt"])))

            for ex_name, target_sets, target_reps in PROGRAMS[program_name]:
                # Occasionally an exercise gets skipped - Q4 should see that.
                if random.random() < 0.08:
                    continue

                ex = ex_lookup[ex_name]
                base, increment = LIFTS[ex_name]

                if ex["equipment"] == "bodyweight":
                    top_weight = 0.0
                else:
                    top_weight = working_weight(base, increment, level, week,
                                                deload_week,
                                                stalling=ex_name in STALLING)

                for set_no in range(target_sets):
                    reps = max(1, target_reps + random.choice([-2, -1, 0, 0, 1]))
                    # Later sets are slightly lighter as fatigue builds.
                    weight = top_weight * (1 - 0.03 * set_no)
                    weight = round_to_plate(weight) if top_weight else 0.0
                    db.call_proc("sp_log_set", (
                        workout_id, ex["exercise_id"], reps, weight,
                        round(random.uniform(6.5, 9.5) * 2) / 2, 0))

            db.execute(
                "UPDATE Workout SET ended_at = %s WHERE workout_id = %s",
                (started + timedelta(minutes=duration), workout_id))


def main():
    ex_lookup = fetch_lookup()
    if not ex_lookup:
        raise SystemExit("Exercise table is empty - run sql/03_seed_static.sql first.")

    user_ids = create_users()
    for username, _name, _g, _h, bodyweight, level in USERS:
        uid = user_ids[username]
        if db.query_one("SELECT 1 AS x FROM Workout WHERE user_id = %s LIMIT 1", (uid,)):
            print(f"  {username}: already has data, skipping")
            continue
        print(f"  {username}: generating {WEEKS} weeks of training...")
        programs = create_programs(uid, ex_lookup)
        seed_history(uid, level, bodyweight, ex_lookup, programs)

    counts = db.query_one("""
        SELECT (SELECT COUNT(*) FROM Users)          AS users,
               (SELECT COUNT(*) FROM Workout)        AS workouts,
               (SELECT COUNT(*) FROM SetEntry)       AS sets,
               (SELECT COUNT(*) FROM PersonalRecord) AS prs""")
    print("\nDone. {users} users, {workouts} workouts, {sets} sets, "
          "{prs} personal records.".format(**counts))
    print("Log in as any username above with the password: password123")


if __name__ == "__main__":
    main()
