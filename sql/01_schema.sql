-- ============================================================
--  GymLog - Training Tracker System
--  DV1703 - Final Project
--  File 1/3: Schema (DDL)
--  Target: MySQL 8.0+ / MariaDB 10.5+
--  Run:  mysql -u root -p < sql/01_schema.sql
-- ============================================================

DROP DATABASE IF EXISTS gymlog;
CREATE DATABASE gymlog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gymlog;

-- ------------------------------------------------------------
-- 1. Users
-- ------------------------------------------------------------
CREATE TABLE Users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(40)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(80)  NOT NULL,
    birth_date    DATE         NULL,
    gender        ENUM('male','female','other') NULL,
    height_cm     DECIMAL(5,1) NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_height CHECK (height_cm IS NULL OR (height_cm BETWEEN 100 AND 250))
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. MuscleGroup  (lookup / classification table)
-- ------------------------------------------------------------
CREATE TABLE MuscleGroup (
    muscle_group_id INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(40) NOT NULL UNIQUE,
    body_region     ENUM('upper','lower','core') NOT NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. Exercise
--    created_by = NULL  -> exercise shipped with the system
--    created_by = user  -> custom exercise made by that user
-- ------------------------------------------------------------
CREATE TABLE Exercise (
    exercise_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(80) NOT NULL UNIQUE,
    muscle_group_id INT         NOT NULL,
    equipment       ENUM('barbell','dumbbell','machine','cable','bodyweight','other')
                    NOT NULL DEFAULT 'other',
    is_compound     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by      INT         NULL,
    CONSTRAINT fk_exercise_musclegroup FOREIGN KEY (muscle_group_id)
        REFERENCES MuscleGroup(muscle_group_id) ON DELETE RESTRICT,
    CONSTRAINT fk_exercise_creator FOREIGN KEY (created_by)
        REFERENCES Users(user_id) ON DELETE SET NULL,
    INDEX idx_exercise_group (muscle_group_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. Program  (a training plan owned by one user)
-- ------------------------------------------------------------
CREATE TABLE Program (
    program_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT         NOT NULL,
    name          VARCHAR(80) NOT NULL,
    description   TEXT        NULL,
    days_per_week TINYINT     NOT NULL DEFAULT 3,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_program_user FOREIGN KEY (user_id)
        REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT uq_program_name UNIQUE (user_id, name),
    CONSTRAINT chk_days CHECK (days_per_week BETWEEN 1 AND 7)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 5. ProgramExercise  (M:N between Program and Exercise,
--                      with the planned sets/reps as attributes)
-- ------------------------------------------------------------
CREATE TABLE ProgramExercise (
    program_id   INT     NOT NULL,
    exercise_id  INT     NOT NULL,
    position     TINYINT NOT NULL,
    target_sets  TINYINT NOT NULL,
    target_reps  TINYINT NOT NULL,
    PRIMARY KEY (program_id, exercise_id),
    CONSTRAINT fk_pe_program FOREIGN KEY (program_id)
        REFERENCES Program(program_id) ON DELETE CASCADE,
    CONSTRAINT fk_pe_exercise FOREIGN KEY (exercise_id)
        REFERENCES Exercise(exercise_id) ON DELETE CASCADE,
    CONSTRAINT chk_target CHECK (target_sets BETWEEN 1 AND 20
                             AND target_reps BETWEEN 1 AND 100)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 6. Workout  (one training session)
--    total_volume_kg is a derived column kept in sync by triggers
-- ------------------------------------------------------------
CREATE TABLE Workout (
    workout_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    program_id      INT          NULL,
    started_at      DATETIME     NOT NULL,
    ended_at        DATETIME     NULL,
    notes           VARCHAR(255) NULL,
    total_volume_kg DECIMAL(12,2) NOT NULL DEFAULT 0,
    CONSTRAINT fk_workout_user FOREIGN KEY (user_id)
        REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_workout_program FOREIGN KEY (program_id)
        REFERENCES Program(program_id) ON DELETE SET NULL,
    INDEX idx_workout_user_date (user_id, started_at)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 7. WorkoutExercise  (which exercises were done in a session)
-- ------------------------------------------------------------
CREATE TABLE WorkoutExercise (
    workout_exercise_id INT AUTO_INCREMENT PRIMARY KEY,
    workout_id          INT     NOT NULL,
    exercise_id         INT     NOT NULL,
    position            TINYINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_we_workout FOREIGN KEY (workout_id)
        REFERENCES Workout(workout_id) ON DELETE CASCADE,
    CONSTRAINT fk_we_exercise FOREIGN KEY (exercise_id)
        REFERENCES Exercise(exercise_id) ON DELETE RESTRICT,
    CONSTRAINT uq_workout_exercise UNIQUE (workout_id, exercise_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 8. SetEntry  (the weak entity at the heart of the system:
--               one performed set = reps x weight)
-- ------------------------------------------------------------
CREATE TABLE SetEntry (
    set_id              INT AUTO_INCREMENT PRIMARY KEY,
    workout_exercise_id INT          NOT NULL,
    set_number          TINYINT      NOT NULL,
    reps                SMALLINT     NOT NULL,
    weight_kg           DECIMAL(6,2) NOT NULL,
    rpe                 DECIMAL(3,1) NULL,
    is_warmup           BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_set_we FOREIGN KEY (workout_exercise_id)
        REFERENCES WorkoutExercise(workout_exercise_id) ON DELETE CASCADE,
    CONSTRAINT uq_set_number UNIQUE (workout_exercise_id, set_number),
    CONSTRAINT chk_reps   CHECK (reps BETWEEN 1 AND 100),
    CONSTRAINT chk_weight CHECK (weight_kg >= 0 AND weight_kg <= 600),
    CONSTRAINT chk_rpe    CHECK (rpe IS NULL OR (rpe BETWEEN 1 AND 10))
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 9. BodyMeasurement  (weekly weigh-in)
-- ------------------------------------------------------------
CREATE TABLE BodyMeasurement (
    measurement_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT          NOT NULL,
    measured_on    DATE         NOT NULL,
    weight_kg      DECIMAL(5,2) NOT NULL,
    body_fat_pct   DECIMAL(4,1) NULL,
    CONSTRAINT fk_bm_user FOREIGN KEY (user_id)
        REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT uq_bm UNIQUE (user_id, measured_on),
    CONSTRAINT chk_bodyweight CHECK (weight_kg BETWEEN 30 AND 300),
    CONSTRAINT chk_bf CHECK (body_fat_pct IS NULL OR (body_fat_pct BETWEEN 3 AND 70))
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 10. PersonalRecord  (derived table, maintained only by triggers)
-- ------------------------------------------------------------
CREATE TABLE PersonalRecord (
    user_id        INT          NOT NULL,
    exercise_id    INT          NOT NULL,
    best_est_1rm   DECIMAL(6,2) NOT NULL,
    best_weight_kg DECIMAL(6,2) NOT NULL,
    best_reps      SMALLINT     NOT NULL,
    achieved_at    DATETIME     NOT NULL,
    set_id         INT          NULL,
    PRIMARY KEY (user_id, exercise_id),
    CONSTRAINT fk_pr_user FOREIGN KEY (user_id)
        REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_pr_exercise FOREIGN KEY (exercise_id)
        REFERENCES Exercise(exercise_id) ON DELETE CASCADE,
    CONSTRAINT fk_pr_set FOREIGN KEY (set_id)
        REFERENCES SetEntry(set_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- View: flattens the set -> exercise -> workout -> user chain.
-- Used by the application to keep the most common joins in one place.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_set_full AS
SELECT  s.set_id,
        s.set_number,
        s.reps,
        s.weight_kg,
        s.rpe,
        s.is_warmup,
        (s.reps * s.weight_kg)      AS volume_kg,
        we.workout_exercise_id,
        we.exercise_id,
        e.name                      AS exercise_name,
        e.equipment,
        mg.muscle_group_id,
        mg.name                     AS muscle_group,
        w.workout_id,
        w.user_id,
        w.started_at
FROM        SetEntry        s
JOIN        WorkoutExercise we ON s.workout_exercise_id = we.workout_exercise_id
JOIN        Workout         w  ON we.workout_id         = w.workout_id
JOIN        Exercise        e  ON we.exercise_id        = e.exercise_id
JOIN        MuscleGroup     mg ON e.muscle_group_id     = mg.muscle_group_id;
