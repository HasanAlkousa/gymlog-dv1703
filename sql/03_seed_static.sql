-- ============================================================
--  GymLog - File 3/3: Static reference data
--  Run:  mysql -u root -p < sql/03_seed_static.sql
-- ============================================================
USE gymlog;

INSERT INTO MuscleGroup (name, body_region) VALUES
    ('Chest',      'upper'),
    ('Back',       'upper'),
    ('Shoulders',  'upper'),
    ('Biceps',     'upper'),
    ('Triceps',    'upper'),
    ('Quadriceps', 'lower'),
    ('Hamstrings', 'lower'),
    ('Glutes',     'lower'),
    ('Calves',     'lower'),
    ('Abs',        'core'),
    ('Lower back', 'core');

INSERT INTO Exercise (name, muscle_group_id, equipment, is_compound) VALUES
    ('Barbell Bench Press',   (SELECT muscle_group_id FROM MuscleGroup WHERE name='Chest'),      'barbell',    TRUE),
    ('Incline Dumbbell Press',(SELECT muscle_group_id FROM MuscleGroup WHERE name='Chest'),      'dumbbell',   TRUE),
    ('Cable Fly',             (SELECT muscle_group_id FROM MuscleGroup WHERE name='Chest'),      'cable',      FALSE),
    ('Deadlift',              (SELECT muscle_group_id FROM MuscleGroup WHERE name='Back'),       'barbell',    TRUE),
    ('Barbell Row',           (SELECT muscle_group_id FROM MuscleGroup WHERE name='Back'),       'barbell',    TRUE),
    ('Lat Pulldown',          (SELECT muscle_group_id FROM MuscleGroup WHERE name='Back'),       'machine',    FALSE),
    ('Pull-up',               (SELECT muscle_group_id FROM MuscleGroup WHERE name='Back'),       'bodyweight', TRUE),
    ('Overhead Press',        (SELECT muscle_group_id FROM MuscleGroup WHERE name='Shoulders'),  'barbell',    TRUE),
    ('Lateral Raise',         (SELECT muscle_group_id FROM MuscleGroup WHERE name='Shoulders'),  'dumbbell',   FALSE),
    ('Face Pull',             (SELECT muscle_group_id FROM MuscleGroup WHERE name='Shoulders'),  'cable',      FALSE),
    ('Barbell Curl',          (SELECT muscle_group_id FROM MuscleGroup WHERE name='Biceps'),     'barbell',    FALSE),
    ('Hammer Curl',           (SELECT muscle_group_id FROM MuscleGroup WHERE name='Biceps'),     'dumbbell',   FALSE),
    ('Triceps Pushdown',      (SELECT muscle_group_id FROM MuscleGroup WHERE name='Triceps'),    'cable',      FALSE),
    ('Close-Grip Bench Press',(SELECT muscle_group_id FROM MuscleGroup WHERE name='Triceps'),    'barbell',    TRUE),
    ('Back Squat',            (SELECT muscle_group_id FROM MuscleGroup WHERE name='Quadriceps'), 'barbell',    TRUE),
    ('Front Squat',           (SELECT muscle_group_id FROM MuscleGroup WHERE name='Quadriceps'), 'barbell',    TRUE),
    ('Leg Press',             (SELECT muscle_group_id FROM MuscleGroup WHERE name='Quadriceps'), 'machine',    TRUE),
    ('Leg Extension',         (SELECT muscle_group_id FROM MuscleGroup WHERE name='Quadriceps'), 'machine',    FALSE),
    ('Romanian Deadlift',     (SELECT muscle_group_id FROM MuscleGroup WHERE name='Hamstrings'), 'barbell',    TRUE),
    ('Leg Curl',              (SELECT muscle_group_id FROM MuscleGroup WHERE name='Hamstrings'), 'machine',    FALSE),
    ('Hip Thrust',            (SELECT muscle_group_id FROM MuscleGroup WHERE name='Glutes'),     'barbell',    TRUE),
    ('Bulgarian Split Squat', (SELECT muscle_group_id FROM MuscleGroup WHERE name='Glutes'),     'dumbbell',   TRUE),
    ('Standing Calf Raise',   (SELECT muscle_group_id FROM MuscleGroup WHERE name='Calves'),     'machine',    FALSE),
    ('Hanging Leg Raise',     (SELECT muscle_group_id FROM MuscleGroup WHERE name='Abs'),        'bodyweight', FALSE),
    ('Cable Crunch',          (SELECT muscle_group_id FROM MuscleGroup WHERE name='Abs'),        'cable',      FALSE),
    ('Plank',                 (SELECT muscle_group_id FROM MuscleGroup WHERE name='Abs'),        'bodyweight', FALSE),
    ('Back Extension',        (SELECT muscle_group_id FROM MuscleGroup WHERE name='Lower back'), 'bodyweight', FALSE);
