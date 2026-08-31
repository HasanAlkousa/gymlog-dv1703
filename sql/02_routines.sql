-- ============================================================
--  GymLog - File 2/3: Functions, Procedures, Triggers
--  Run:  mysql -u root -p < sql/02_routines.sql
-- ============================================================
USE gymlog;

DROP FUNCTION IF EXISTS fn_estimated_1rm;
DROP FUNCTION IF EXISTS fn_weekly_volume;
DROP PROCEDURE IF EXISTS sp_start_workout_from_program;
DROP PROCEDURE IF EXISTS sp_log_set;
DROP PROCEDURE IF EXISTS sp_finish_workout;
DROP TRIGGER IF EXISTS trg_set_before_insert;
DROP TRIGGER IF EXISTS trg_set_after_insert;
DROP TRIGGER IF EXISTS trg_set_after_delete;
DROP TRIGGER IF EXISTS trg_workout_before_update;

DELIMITER $$

-- ============================================================
-- FUNCTION 1: fn_estimated_1rm
-- Epley's formula: 1RM = w * (1 + reps/30).
-- Lets us compare a set of 5x100 kg with a set of 8x85 kg on the
-- same scale, which is what all progression tracking builds on.
-- ============================================================
CREATE FUNCTION fn_estimated_1rm(p_weight DECIMAL(6,2), p_reps SMALLINT)
RETURNS DECIMAL(6,2)
DETERMINISTIC
NO SQL
BEGIN
    IF p_weight IS NULL OR p_reps IS NULL OR p_reps < 1 THEN
        RETURN 0;
    END IF;
    IF p_reps = 1 THEN
        RETURN p_weight;
    END IF;
    RETURN ROUND(p_weight * (1 + (p_reps / 30.0)), 2);
END$$

-- ============================================================
-- FUNCTION 2: fn_weekly_volume
-- Total training volume (kg lifted) for one user in one ISO week.
-- Used in the dashboard and by the "is the user overreaching?"
-- comparison between this week and the 4-week average.
-- ============================================================
CREATE FUNCTION fn_weekly_volume(p_user_id INT, p_date DATE)
RETURNS DECIMAL(12,2)
READS SQL DATA
BEGIN
    DECLARE v_total DECIMAL(12,2);

    SELECT COALESCE(SUM(s.reps * s.weight_kg), 0)
      INTO v_total
      FROM SetEntry        s
      JOIN WorkoutExercise we ON s.workout_exercise_id = we.workout_exercise_id
      JOIN Workout         w  ON we.workout_id         = w.workout_id
     WHERE w.user_id  = p_user_id
       AND s.is_warmup = FALSE
       AND YEARWEEK(w.started_at, 3) = YEARWEEK(p_date, 3);

    RETURN v_total;
END$$

-- ============================================================
-- PROCEDURE 1: sp_start_workout_from_program
-- Creates a new session and copies every exercise of the chosen
-- program into WorkoutExercise, in the planned order.
-- Without this the application would need one INSERT per exercise
-- in a loop; here it is one atomic call.
-- ============================================================
CREATE PROCEDURE sp_start_workout_from_program(
    IN  p_user_id    INT,
    IN  p_program_id INT,
    OUT p_workout_id INT
)
MODIFIES SQL DATA
BEGIN
    DECLARE v_owner INT;

    -- A user may only start a session from a program they own.
    SELECT user_id INTO v_owner FROM Program WHERE program_id = p_program_id;

    IF v_owner IS NULL OR v_owner <> p_user_id THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Program does not exist or belongs to another user';
    END IF;

    INSERT INTO Workout (user_id, program_id, started_at)
    VALUES (p_user_id, p_program_id, NOW());

    SET p_workout_id = LAST_INSERT_ID();

    INSERT INTO WorkoutExercise (workout_id, exercise_id, position)
    SELECT p_workout_id, pe.exercise_id, pe.position
      FROM ProgramExercise pe
     WHERE pe.program_id = p_program_id
     ORDER BY pe.position;
END$$

-- ============================================================
-- PROCEDURE 2: sp_log_set
-- Logs one set. Finds the WorkoutExercise row (creates it if the
-- user adds an exercise that was not in the program) and computes
-- the next set number, so the application never has to.
-- ============================================================
CREATE PROCEDURE sp_log_set(
    IN p_workout_id  INT,
    IN p_exercise_id INT,
    IN p_reps        SMALLINT,
    IN p_weight      DECIMAL(6,2),
    IN p_rpe         DECIMAL(3,1),
    IN p_is_warmup   BOOLEAN
)
MODIFIES SQL DATA
BEGIN
    DECLARE v_we_id      INT DEFAULT NULL;
    DECLARE v_next_set   TINYINT;
    DECLARE v_next_pos   TINYINT;

    SELECT workout_exercise_id INTO v_we_id
      FROM WorkoutExercise
     WHERE workout_id = p_workout_id AND exercise_id = p_exercise_id;

    IF v_we_id IS NULL THEN
        SELECT COALESCE(MAX(position), 0) + 1 INTO v_next_pos
          FROM WorkoutExercise WHERE workout_id = p_workout_id;

        INSERT INTO WorkoutExercise (workout_id, exercise_id, position)
        VALUES (p_workout_id, p_exercise_id, v_next_pos);

        SET v_we_id = LAST_INSERT_ID();
    END IF;

    SELECT COALESCE(MAX(set_number), 0) + 1 INTO v_next_set
      FROM SetEntry WHERE workout_exercise_id = v_we_id;

    INSERT INTO SetEntry (workout_exercise_id, set_number, reps, weight_kg, rpe, is_warmup)
    VALUES (v_we_id, v_next_set, p_reps, p_weight, p_rpe, COALESCE(p_is_warmup, FALSE));
END$$

-- ============================================================
-- PROCEDURE 3: sp_finish_workout
-- Closes a session and removes exercises that were planned but
-- never performed, so the history is not polluted by empty rows.
-- ============================================================
CREATE PROCEDURE sp_finish_workout(IN p_workout_id INT, IN p_notes VARCHAR(255))
MODIFIES SQL DATA
BEGIN
    DELETE we FROM WorkoutExercise we
     WHERE we.workout_id = p_workout_id
       AND NOT EXISTS (SELECT 1 FROM SetEntry s
                        WHERE s.workout_exercise_id = we.workout_exercise_id);

    UPDATE Workout
       SET ended_at = NOW(),
           notes    = COALESCE(p_notes, notes)
     WHERE workout_id = p_workout_id;
END$$

-- ============================================================
-- TRIGGER 1: trg_set_before_insert
-- Business rules that a CHECK constraint cannot express, because
-- they depend on another table (bodyweight exercises may be
-- logged with 0 kg, everything else may not).
-- ============================================================
CREATE TRIGGER trg_set_before_insert
BEFORE INSERT ON SetEntry
FOR EACH ROW
BEGIN
    DECLARE v_equipment VARCHAR(20);

    SELECT e.equipment INTO v_equipment
      FROM WorkoutExercise we
      JOIN Exercise e ON we.exercise_id = e.exercise_id
     WHERE we.workout_exercise_id = NEW.workout_exercise_id;

    IF NEW.weight_kg = 0 AND v_equipment <> 'bodyweight' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Weight 0 kg is only allowed for bodyweight exercises';
    END IF;
END$$

-- ============================================================
-- TRIGGER 2: trg_set_after_insert
--   (a) keeps Workout.total_volume_kg in sync
--   (b) maintains PersonalRecord automatically
-- The PR table is pure derived data - the application never
-- writes to it, which makes it impossible for the UI to show a
-- record that was not actually lifted.
-- ============================================================
CREATE TRIGGER trg_set_after_insert
AFTER INSERT ON SetEntry
FOR EACH ROW
BEGIN
    DECLARE v_user_id     INT;
    DECLARE v_exercise_id INT;
    DECLARE v_workout_id  INT;
    DECLARE v_started_at  DATETIME;
    DECLARE v_1rm         DECIMAL(6,2);
    DECLARE v_old_1rm     DECIMAL(6,2) DEFAULT NULL;

    SELECT w.workout_id, w.user_id, we.exercise_id, w.started_at
      INTO v_workout_id, v_user_id, v_exercise_id, v_started_at
      FROM WorkoutExercise we
      JOIN Workout w ON we.workout_id = w.workout_id
     WHERE we.workout_exercise_id = NEW.workout_exercise_id;

    -- (a) derived volume
    UPDATE Workout
       SET total_volume_kg = total_volume_kg + (NEW.reps * NEW.weight_kg)
     WHERE workout_id = v_workout_id;

    -- (b) personal record (warm-up sets never count)
    IF NEW.is_warmup = FALSE THEN
        SET v_1rm = fn_estimated_1rm(NEW.weight_kg, NEW.reps);

        SELECT best_est_1rm INTO v_old_1rm
          FROM PersonalRecord
         WHERE user_id = v_user_id AND exercise_id = v_exercise_id;

        IF v_old_1rm IS NULL THEN
            INSERT INTO PersonalRecord
                (user_id, exercise_id, best_est_1rm, best_weight_kg,
                 best_reps, achieved_at, set_id)
            VALUES
                (v_user_id, v_exercise_id, v_1rm, NEW.weight_kg,
                 NEW.reps, v_started_at, NEW.set_id);
        ELSEIF v_1rm > v_old_1rm THEN
            UPDATE PersonalRecord
               SET best_est_1rm   = v_1rm,
                   best_weight_kg = NEW.weight_kg,
                   best_reps      = NEW.reps,
                   achieved_at    = v_started_at,
                   set_id         = NEW.set_id
             WHERE user_id = v_user_id AND exercise_id = v_exercise_id;
        END IF;
    END IF;
END$$

-- ============================================================
-- TRIGGER 3: trg_set_after_delete
-- Keeps the derived volume correct when a mistyped set is removed.
-- ============================================================
CREATE TRIGGER trg_set_after_delete
AFTER DELETE ON SetEntry
FOR EACH ROW
BEGIN
    UPDATE Workout w
      JOIN WorkoutExercise we ON we.workout_id = w.workout_id
       SET w.total_volume_kg = GREATEST(
               w.total_volume_kg - (OLD.reps * OLD.weight_kg), 0)
     WHERE we.workout_exercise_id = OLD.workout_exercise_id;
END$$

-- ============================================================
-- TRIGGER 4: trg_workout_before_update
-- A session cannot end before it started.
-- ============================================================
CREATE TRIGGER trg_workout_before_update
BEFORE UPDATE ON Workout
FOR EACH ROW
BEGIN
    IF NEW.ended_at IS NOT NULL AND NEW.ended_at < NEW.started_at THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'ended_at cannot be earlier than started_at';
    END IF;
END$$

DELIMITER ;
