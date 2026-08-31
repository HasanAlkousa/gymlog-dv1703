"""
Every SQL statement the application uses lives here.

Keeping them in one module (instead of scattered through the Flask
routes) makes it easy to review them, to explain them in the report and
to see that no ORM is involved: what is sent to MySQL is exactly what is
written below, with values bound through %s placeholders.

The six queries named Q1..Q6 are the ones discussed in the report.
"""

# ------------------------------------------------------------------
# Authentication / users
# ------------------------------------------------------------------
GET_USER_BY_USERNAME = """
    SELECT user_id, username, email, password_hash, full_name
      FROM Users
     WHERE username = %s
"""

CREATE_USER = """
    INSERT INTO Users (username, email, password_hash, full_name, birth_date, gender, height_cm)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

# ==================================================================
# Q1  Volume per muscle group  (multirelation, 5 tables, JOIN,
#     aggregation + GROUP BY)
#     "Am I training my whole body, or only the mirror muscles?"
# ==================================================================
Q1_VOLUME_PER_MUSCLE_GROUP = """
    SELECT  mg.name                              AS muscle_group,
            mg.body_region                       AS body_region,
            COUNT(DISTINCT w.workout_id)         AS sessions,
            COUNT(s.set_id)                      AS total_sets,
            SUM(s.reps)                          AS total_reps,
            ROUND(SUM(s.reps * s.weight_kg))     AS volume_kg
      FROM  SetEntry        s
      JOIN  WorkoutExercise we ON s.workout_exercise_id = we.workout_exercise_id
      JOIN  Workout         w  ON we.workout_id         = w.workout_id
      JOIN  Exercise        e  ON we.exercise_id        = e.exercise_id
      JOIN  MuscleGroup     mg ON e.muscle_group_id     = mg.muscle_group_id
     WHERE  w.user_id   = %s
       AND  s.is_warmup = FALSE
       AND  w.started_at >= (CURDATE() - INTERVAL %s DAY)
     GROUP BY mg.muscle_group_id, mg.name, mg.body_region
     ORDER BY volume_kg DESC
"""

# ==================================================================
# Q2  Week-by-week progression for one exercise
#     (multirelation, JOIN, GROUP BY on a derived key, and it calls
#      the stored function fn_estimated_1rm)
#     This is the data behind the progression chart.
# ==================================================================
Q2_EXERCISE_PROGRESSION = """
    SELECT  YEARWEEK(w.started_at, 3)                        AS iso_week,
            MIN(DATE(w.started_at))                          AS week_start,
            COUNT(DISTINCT w.workout_id)                     AS sessions,
            COUNT(s.set_id)                                  AS working_sets,
            ROUND(SUM(s.reps * s.weight_kg))                 AS volume_kg,
            MAX(s.weight_kg)                                 AS heaviest_kg,
            MAX(fn_estimated_1rm(s.weight_kg, s.reps))       AS best_est_1rm
      FROM  SetEntry        s
      JOIN  WorkoutExercise we ON s.workout_exercise_id = we.workout_exercise_id
      JOIN  Workout         w  ON we.workout_id         = w.workout_id
     WHERE  w.user_id     = %s
       AND  we.exercise_id = %s
       AND  s.is_warmup    = FALSE
       AND  w.started_at  >= (CURDATE() - INTERVAL %s WEEK)
     GROUP BY YEARWEEK(w.started_at, 3)
     ORDER BY iso_week
"""

# ==================================================================
# Q3  Stalled exercises  (JOIN + GROUP BY + HAVING + correlated
#     comparison against the trigger-maintained PR table)
#     "Which lifts have I trained regularly for two months without
#      beating my record?"  -> the app suggests a deload for these.
# ==================================================================
Q3_STALLED_EXERCISES = """
    SELECT  e.name                                       AS exercise,
            mg.name                                      AS muscle_group,
            COUNT(DISTINCT w.workout_id)                 AS sessions_8w,
            MAX(fn_estimated_1rm(s.weight_kg, s.reps))   AS best_1rm_8w,
            pr.best_est_1rm                              AS all_time_1rm,
            DATEDIFF(CURDATE(), DATE(pr.achieved_at))    AS days_since_pr
      FROM  SetEntry        s
      JOIN  WorkoutExercise we ON s.workout_exercise_id = we.workout_exercise_id
      JOIN  Workout         w  ON we.workout_id         = w.workout_id
      JOIN  Exercise        e  ON we.exercise_id        = e.exercise_id
      JOIN  MuscleGroup     mg ON e.muscle_group_id     = mg.muscle_group_id
      JOIN  PersonalRecord  pr ON pr.user_id     = w.user_id
                              AND pr.exercise_id = e.exercise_id
     WHERE  w.user_id    = %s
       AND  s.is_warmup  = FALSE
       AND  w.started_at >= (CURDATE() - INTERVAL 8 WEEK)
     GROUP BY e.exercise_id, e.name, mg.name, pr.best_est_1rm, pr.achieved_at
    HAVING  COUNT(DISTINCT w.workout_id) >= 3
       AND  MAX(fn_estimated_1rm(s.weight_kg, s.reps)) < pr.best_est_1rm
     ORDER BY days_since_pr DESC
"""

# ==================================================================
# Q4  Program adherence  (LEFT JOIN from the plan to reality +
#     aggregation; the LEFT JOIN is what makes skipped exercises
#     visible instead of silently disappearing)
# ==================================================================
Q4_PROGRAM_ADHERENCE = """
    SELECT  e.name                                        AS exercise,
            pe.target_sets                                AS planned_sets,
            pe.target_reps                                AS planned_reps,
            COUNT(s.set_id)                               AS performed_sets,
            COALESCE(ROUND(AVG(s.reps), 1), 0)            AS avg_reps,
            COUNT(DISTINCT w.workout_id)                  AS sessions,
            ROUND(100 * COUNT(s.set_id) /
                  NULLIF(pe.target_sets * COUNT(DISTINCT w.workout_id), 0), 0)
                                                          AS adherence_pct
      FROM  ProgramExercise pe
      JOIN  Exercise        e  ON pe.exercise_id = e.exercise_id
      LEFT JOIN Workout     w  ON w.program_id = pe.program_id
                              AND w.user_id    = %s
                              AND w.started_at >= (CURDATE() - INTERVAL %s DAY)
      LEFT JOIN WorkoutExercise we ON we.workout_id  = w.workout_id
                                  AND we.exercise_id = pe.exercise_id
      LEFT JOIN SetEntry    s  ON s.workout_exercise_id = we.workout_exercise_id
                              AND s.is_warmup = FALSE
     WHERE  pe.program_id = %s
     GROUP BY pe.exercise_id, e.name, pe.target_sets, pe.target_reps, pe.position
     ORDER BY pe.position
"""

# ==================================================================
# Q5  Relative strength ranking  (multirelation with a subquery in
#     the FROM clause: each user's most recent body weight)
#     Strength divided by body weight is the only fair way to compare
#     a 65 kg lifter with a 95 kg lifter.
# ==================================================================
Q5_RELATIVE_STRENGTH = """
    SELECT  u.username,
            u.full_name,
            pr.best_est_1rm                                   AS est_1rm,
            latest.weight_kg                                  AS bodyweight_kg,
            ROUND(pr.best_est_1rm / latest.weight_kg, 2)      AS strength_ratio,
            DATE(pr.achieved_at)                              AS achieved_on
      FROM  PersonalRecord pr
      JOIN  Users    u ON pr.user_id     = u.user_id
      JOIN  Exercise e ON pr.exercise_id = e.exercise_id
      JOIN  (SELECT b.user_id, b.weight_kg
               FROM BodyMeasurement b
               JOIN (SELECT user_id, MAX(measured_on) AS measured_on
                       FROM BodyMeasurement
                      GROUP BY user_id) last
                 ON b.user_id = last.user_id
                AND b.measured_on = last.measured_on) latest
            ON latest.user_id = u.user_id
     WHERE  e.exercise_id = %s
     ORDER BY strength_ratio DESC
     LIMIT 10
"""

# ==================================================================
# Q6  Training consistency  (aggregation over sessions, no set-level
#     rows; feeds the "sessions per week" bar chart and the
#     average session length)
# ==================================================================
Q6_WEEKLY_CONSISTENCY = """
    SELECT  YEARWEEK(w.started_at, 3)                              AS iso_week,
            MIN(DATE(w.started_at))                                AS week_start,
            COUNT(*)                                               AS sessions,
            ROUND(AVG(TIMESTAMPDIFF(MINUTE, w.started_at, w.ended_at))) AS avg_minutes,
            ROUND(SUM(w.total_volume_kg))                          AS volume_kg
      FROM  Workout w
     WHERE  w.user_id   = %s
       AND  w.ended_at IS NOT NULL
       AND  w.started_at >= (CURDATE() - INTERVAL %s WEEK)
     GROUP BY YEARWEEK(w.started_at, 3)
     ORDER BY iso_week
"""

# ------------------------------------------------------------------
# Supporting queries used by the interface
# ------------------------------------------------------------------
LIST_EXERCISES = """
    SELECT e.exercise_id, e.name, e.equipment, e.is_compound,
           mg.name AS muscle_group, mg.body_region
      FROM Exercise    e
      JOIN MuscleGroup mg ON e.muscle_group_id = mg.muscle_group_id
     WHERE e.created_by IS NULL OR e.created_by = %s
     ORDER BY mg.name, e.name
"""

LIST_RECENT_WORKOUTS = """
    SELECT w.workout_id, w.started_at, w.ended_at, w.notes,
           w.total_volume_kg,
           TIMESTAMPDIFF(MINUTE, w.started_at, w.ended_at) AS minutes,
           p.name AS program_name,
           COUNT(DISTINCT we.exercise_id) AS exercises,
           COUNT(s.set_id)                AS sets
      FROM Workout w
      LEFT JOIN Program         p  ON w.program_id = p.program_id
      LEFT JOIN WorkoutExercise we ON we.workout_id = w.workout_id
      LEFT JOIN SetEntry        s  ON s.workout_exercise_id = we.workout_exercise_id
     WHERE w.user_id = %s
     GROUP BY w.workout_id, w.started_at, w.ended_at, w.notes,
              w.total_volume_kg, p.name
     ORDER BY w.started_at DESC
     LIMIT %s
"""

GET_WORKOUT = """
    SELECT w.workout_id, w.user_id, w.started_at, w.ended_at, w.notes,
           w.total_volume_kg, p.name AS program_name, w.program_id
      FROM Workout w
      LEFT JOIN Program p ON w.program_id = p.program_id
     WHERE w.workout_id = %s AND w.user_id = %s
"""

GET_WORKOUT_SETS = """
    SELECT we.workout_exercise_id, we.position, we.exercise_id,
           e.name AS exercise_name, mg.name AS muscle_group,
           e.equipment,
           s.set_id, s.set_number, s.reps, s.weight_kg, s.rpe, s.is_warmup,
           fn_estimated_1rm(s.weight_kg, s.reps) AS est_1rm,
           pr.set_id IS NOT NULL AND pr.set_id = s.set_id AS is_pr
      FROM WorkoutExercise we
      JOIN Exercise    e  ON we.exercise_id      = e.exercise_id
      JOIN MuscleGroup mg ON e.muscle_group_id   = mg.muscle_group_id
      LEFT JOIN SetEntry s ON s.workout_exercise_id = we.workout_exercise_id
      LEFT JOIN PersonalRecord pr ON pr.exercise_id = we.exercise_id
                                 AND pr.user_id     = %s
     WHERE we.workout_id = %s
     ORDER BY we.position, s.set_number
"""

GET_PERSONAL_RECORDS = """
    SELECT e.name AS exercise, mg.name AS muscle_group,
           pr.best_est_1rm, pr.best_weight_kg, pr.best_reps,
           DATE(pr.achieved_at) AS achieved_on
      FROM PersonalRecord pr
      JOIN Exercise    e  ON pr.exercise_id    = e.exercise_id
      JOIN MuscleGroup mg ON e.muscle_group_id = mg.muscle_group_id
     WHERE pr.user_id = %s
     ORDER BY pr.best_est_1rm DESC
"""

LIST_PROGRAMS = """
    SELECT p.program_id, p.name, p.description, p.days_per_week, p.is_active,
           COUNT(pe.exercise_id) AS exercise_count
      FROM Program p
      LEFT JOIN ProgramExercise pe ON p.program_id = pe.program_id
     WHERE p.user_id = %s
     GROUP BY p.program_id, p.name, p.description, p.days_per_week, p.is_active
     ORDER BY p.is_active DESC, p.name
"""

GET_PROGRAM_EXERCISES = """
    SELECT pe.position, pe.target_sets, pe.target_reps,
           e.exercise_id, e.name AS exercise_name, mg.name AS muscle_group
      FROM ProgramExercise pe
      JOIN Exercise    e  ON pe.exercise_id    = e.exercise_id
      JOIN MuscleGroup mg ON e.muscle_group_id = mg.muscle_group_id
     WHERE pe.program_id = %s
     ORDER BY pe.position
"""

GET_BODY_MEASUREMENTS = """
    SELECT measured_on, weight_kg, body_fat_pct
      FROM BodyMeasurement
     WHERE user_id = %s
     ORDER BY measured_on
"""

INSERT_BODY_MEASUREMENT = """
    INSERT INTO BodyMeasurement (user_id, measured_on, weight_kg, body_fat_pct)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE weight_kg = VALUES(weight_kg),
                            body_fat_pct = VALUES(body_fat_pct)
"""

DELETE_SET = """
    DELETE s FROM SetEntry s
      JOIN WorkoutExercise we ON s.workout_exercise_id = we.workout_exercise_id
      JOIN Workout         w  ON we.workout_id = w.workout_id
     WHERE s.set_id = %s AND w.user_id = %s
"""

# Dashboard summary: this week's volume via the stored function.
DASHBOARD_SUMMARY = """
    SELECT fn_weekly_volume(%s, CURDATE())                  AS volume_this_week,
           fn_weekly_volume(%s, CURDATE() - INTERVAL 1 WEEK) AS volume_last_week,
           (SELECT COUNT(*) FROM Workout
             WHERE user_id = %s
               AND YEARWEEK(started_at, 3) = YEARWEEK(CURDATE(), 3)) AS sessions_this_week,
           (SELECT COUNT(*) FROM Workout WHERE user_id = %s)         AS sessions_total,
           (SELECT COUNT(*) FROM PersonalRecord WHERE user_id = %s)  AS pr_count
"""

OPEN_WORKOUT = """
    SELECT workout_id FROM Workout
     WHERE user_id = %s AND ended_at IS NULL
     ORDER BY started_at DESC LIMIT 1
"""
