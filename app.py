"""
GymLog - a training tracker built for DV1703.

Flask + mysql-connector. No ORM: every statement comes from queries.py
or is a call to a stored procedure.
"""
import os
from datetime import date, datetime

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db
import queries as q

app = Flask(__name__)
app.secret_key = os.getenv("GYMLOG_SECRET", "dev-secret-change-me")


# ------------------------------------------------------------------
# Session helpers
# ------------------------------------------------------------------
def current_user_id():
    return session.get("user_id")


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user_id():
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    return {"username": session.get("username"),
            "full_name": session.get("full_name")}


# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = db.query_one(q.GET_USER_BY_USERNAME, (request.form["username"],))
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        try:
            db.execute(q.CREATE_USER, (
                f["username"], f["email"],
                generate_password_hash(f["password"]),
                f["full_name"],
                f.get("birth_date") or None,
                f.get("gender") or None,
                f.get("height_cm") or None,
            ))
            flash("Account created. Log in to start training.", "ok")
            return redirect(url_for("login"))
        except Exception as exc:
            flash(f"Could not create the account: {exc}", "error")
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    uid = current_user_id()
    summary = db.query_one(q.DASHBOARD_SUMMARY, (uid, uid, uid, uid, uid))
    recent = db.query_all(q.LIST_RECENT_WORKOUTS, (uid, 5))
    balance = db.query_all(q.Q1_VOLUME_PER_MUSCLE_GROUP, (uid, 30))
    stalled = db.query_all(q.Q3_STALLED_EXERCISES, (uid,))
    records = db.query_all(q.GET_PERSONAL_RECORDS, (uid,))[:6]
    open_workout = db.query_one(q.OPEN_WORKOUT, (uid,))

    change = None
    if summary and summary["volume_last_week"]:
        change = round(
            100 * (float(summary["volume_this_week"]) - float(summary["volume_last_week"]))
            / float(summary["volume_last_week"])
        )

    return render_template(
        "dashboard.html", summary=summary, recent=recent, balance=balance,
        stalled=stalled, records=records, change=change,
        open_workout=open_workout,
        programs=db.query_all(q.LIST_PROGRAMS, (uid,)),
    )


# ------------------------------------------------------------------
# Workouts
# ------------------------------------------------------------------
@app.route("/workouts")
@login_required
def workouts():
    uid = current_user_id()
    return render_template("workouts.html",
                           workouts=db.query_all(q.LIST_RECENT_WORKOUTS, (uid, 50)),
                           programs=db.query_all(q.LIST_PROGRAMS, (uid,)))


@app.route("/workouts/start", methods=["POST"])
@login_required
def start_workout():
    uid = current_user_id()
    program_id = request.form.get("program_id")

    if program_id:
        # PROCEDURE: creates the session and copies the plan in one call.
        out = db.call_proc("sp_start_workout_from_program",
                           (uid, int(program_id), 0))
        workout_id = out[2]
    else:
        workout_id = db.execute(
            "INSERT INTO Workout (user_id, started_at) VALUES (%s, NOW())", (uid,))

    return redirect(url_for("workout_detail", workout_id=workout_id))


@app.route("/workouts/<int:workout_id>")
@login_required
def workout_detail(workout_id):
    uid = current_user_id()
    workout = db.query_one(q.GET_WORKOUT, (workout_id, uid))
    if not workout:
        flash("That session does not exist.", "error")
        return redirect(url_for("workouts"))

    rows = db.query_all(q.GET_WORKOUT_SETS, (uid, workout_id))

    # Group the flat rows into one block per exercise.
    blocks = {}
    for r in rows:
        block = blocks.setdefault(r["workout_exercise_id"], {
            "exercise_id": r["exercise_id"],
            "exercise_name": r["exercise_name"],
            "muscle_group": r["muscle_group"],
            "equipment": r["equipment"],
            "sets": [],
        })
        if r["set_id"] is not None:
            block["sets"].append(r)

    return render_template("workout_detail.html",
                           workout=workout,
                           blocks=list(blocks.values()),
                           exercises=db.query_all(q.LIST_EXERCISES, (uid,)))


@app.route("/workouts/<int:workout_id>/sets", methods=["POST"])
@login_required
def log_set(workout_id):
    uid = current_user_id()
    if not db.query_one(q.GET_WORKOUT, (workout_id, uid)):
        flash("That session does not exist.", "error")
        return redirect(url_for("workouts"))

    f = request.form
    try:
        # PROCEDURE: picks the next set number and creates the
        # WorkoutExercise row if the exercise is new to this session.
        db.call_proc("sp_log_set", (
            workout_id,
            int(f["exercise_id"]),
            int(f["reps"]),
            float(f["weight_kg"]),
            float(f["rpe"]) if f.get("rpe") else None,
            1 if f.get("is_warmup") else 0,
        ))
    except Exception as exc:
        flash(str(exc), "error")

    return redirect(url_for("workout_detail", workout_id=workout_id))


@app.route("/sets/<int:set_id>/delete", methods=["POST"])
@login_required
def delete_set(set_id):
    db.execute(q.DELETE_SET, (set_id, current_user_id()))
    return redirect(request.referrer or url_for("workouts"))


@app.route("/workouts/<int:workout_id>/finish", methods=["POST"])
@login_required
def finish_workout(workout_id):
    uid = current_user_id()
    if db.query_one(q.GET_WORKOUT, (workout_id, uid)):
        db.call_proc("sp_finish_workout", (workout_id, request.form.get("notes") or None))
        flash("Session saved.", "ok")
    return redirect(url_for("workout_detail", workout_id=workout_id))


# ------------------------------------------------------------------
# Programs, records, statistics, body weight
# ------------------------------------------------------------------
@app.route("/programs")
@login_required
def programs():
    uid = current_user_id()
    plans = db.query_all(q.LIST_PROGRAMS, (uid,))
    for p in plans:
        p["exercises"] = db.query_all(q.GET_PROGRAM_EXERCISES, (p["program_id"],))
        p["adherence"] = db.query_all(q.Q4_PROGRAM_ADHERENCE, (uid, 30, p["program_id"]))
    return render_template("programs.html", programs=plans)


@app.route("/records")
@login_required
def records():
    uid = current_user_id()
    return render_template("records.html",
                           records=db.query_all(q.GET_PERSONAL_RECORDS, (uid,)))


@app.route("/statistics")
@login_required
def statistics():
    uid = current_user_id()
    exercises = db.query_all(q.LIST_EXERCISES, (uid,))
    exercise_id = int(request.args.get("exercise_id") or exercises[0]["exercise_id"])

    return render_template(
        "statistics.html",
        exercises=exercises,
        selected=exercise_id,
        progression=db.query_all(q.Q2_EXERCISE_PROGRESSION, (uid, exercise_id, 16)),
        consistency=db.query_all(q.Q6_WEEKLY_CONSISTENCY, (uid, 12)),
        balance=db.query_all(q.Q1_VOLUME_PER_MUSCLE_GROUP, (uid, 90)),
        ranking=db.query_all(q.Q5_RELATIVE_STRENGTH, (exercise_id,)),
    )


@app.route("/body", methods=["GET", "POST"])
@login_required
def body():
    uid = current_user_id()
    if request.method == "POST":
        f = request.form
        try:
            db.execute(q.INSERT_BODY_MEASUREMENT, (
                uid, f["measured_on"], f["weight_kg"],
                f.get("body_fat_pct") or None))
            flash("Weigh-in saved.", "ok")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("body"))

    return render_template("body.html",
                           measurements=db.query_all(q.GET_BODY_MEASUREMENTS, (uid,)),
                           today=date.today().isoformat())


@app.route("/api/progression/<int:exercise_id>")
@login_required
def api_progression(exercise_id):
    rows = db.query_all(q.Q2_EXERCISE_PROGRESSION,
                        (current_user_id(), exercise_id, 16))
    return jsonify([
        {"week": str(r["week_start"]),
         "est_1rm": float(r["best_est_1rm"] or 0),
         "volume": float(r["volume_kg"] or 0)}
        for r in rows
    ])


@app.template_filter("kg")
def fmt_kg(value):
    if value is None:
        return "-"
    return f"{float(value):,.0f}".replace(",", " ")


@app.template_filter("dt")
def fmt_dt(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%a %d %b")
    return value or ""


if __name__ == "__main__":
    app.run(debug=True, port=5000)
