"""Draws the E/R diagram as an SVG so it can be dropped straight into the report."""

W, H = 1060, 790
BOX_W = 220
INK, RULE, SOFT, ACCENT = "#171d24", "#c9cfc7", "#616b76", "#a83c2c"

ENTITIES = {
    # name: (x, y, [(tag, attribute), ...])
    "Users": (40, 40, [
        ("PK", "user_id"), ("", "username"), ("", "email"), ("", "password_hash"),
        ("", "full_name"), ("", "birth_date"), ("", "gender"), ("", "height_cm"),
        ("", "created_at")]),
    "Program": (40, 250, [
        ("PK", "program_id"), ("FK", "user_id"), ("", "name"), ("", "description"),
        ("", "days_per_week"), ("", "is_active"), ("", "created_at")]),
    "ProgramExercise": (40, 420, [
        ("PK/FK", "program_id"), ("PK/FK", "exercise_id"), ("", "position"),
        ("", "target_sets"), ("", "target_reps")]),
    "BodyMeasurement": (40, 600, [
        ("PK", "measurement_id"), ("FK", "user_id"), ("", "measured_on"),
        ("", "weight_kg"), ("", "body_fat_pct")]),
    "Workout": (380, 40, [
        ("PK", "workout_id"), ("FK", "user_id"), ("FK", "program_id"),
        ("", "started_at"), ("", "ended_at"), ("", "notes"),
        ("D", "total_volume_kg")]),
    "WorkoutExercise": (380, 250, [
        ("PK", "workout_exercise_id"), ("FK", "workout_id"),
        ("FK", "exercise_id"), ("", "position")]),
    "SetEntry": (380, 420, [
        ("PK", "set_id"), ("FK", "workout_exercise_id"), ("", "set_number"),
        ("", "reps"), ("", "weight_kg"), ("", "rpe"), ("", "is_warmup")]),
    "MuscleGroup": (740, 60, [
        ("PK", "muscle_group_id"), ("", "name"), ("", "body_region")]),
    "Exercise": (740, 250, [
        ("PK", "exercise_id"), ("", "name"), ("FK", "muscle_group_id"),
        ("", "equipment"), ("", "is_compound"), ("FK", "created_by")]),
    "PersonalRecord": (740, 460, [
        ("PK/FK", "user_id"), ("PK/FK", "exercise_id"), ("D", "best_est_1rm"),
        ("D", "best_weight_kg"), ("D", "best_reps"), ("D", "achieved_at"),
        ("FK", "set_id")]),
}

# (points, label at start, label at end, dashed)
EDGES = [
    ([(260, 80), (380, 80)], "1", "N", False),                       # Users - Workout
    ([(150, 211), (150, 250)], "1", "N", False),                     # Users - Program
    ([(150, 391), (150, 420)], "1", "N", False),                     # Program - ProgramExercise
    ([(40, 150), (18, 150), (18, 655), (40, 655)], "1", "N", False),  # Users - BodyMeasurement
    ([(260, 300), (345, 300), (345, 150), (380, 150)], "0..1", "N", False),  # Program - Workout
    ([(260, 190), (320, 190), (320, 730), (855, 730), (855, 601)], "1", "N", False),  # Users - PR
    ([(490, 181), (490, 250)], "1", "N", False),                     # Workout - WorkoutExercise
    ([(490, 346), (490, 420)], "1", "N", False),                     # WorkoutExercise - SetEntry
    ([(740, 300), (600, 300)], "1", "N", False),                     # Exercise - WorkoutExercise
    ([(850, 141), (850, 250)], "1", "N", False),                     # MuscleGroup - Exercise
    ([(900, 376), (900, 460)], "1", "N", False),                     # Exercise - PersonalRecord
    ([(200, 531), (200, 580), (700, 580), (700, 330), (740, 330)], "N", "1", False),
    ([(600, 520), (740, 520)], "0..1", "1", True),                   # SetEntry - PersonalRecord
    ([(960, 300), (1015, 300), (1015, 20), (150, 20), (150, 40)], "N", "0..1", True),
]

HEADER_H, LINE_H, PAD = 26, 15, 8


def box_height(attrs):
    return HEADER_H + len(attrs) * LINE_H + PAD


def render():
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="Inter, Helvetica, Arial, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
    ]

    # edges first, so the boxes sit on top of them
    for points, lstart, lend, dashed in EDGES:
        path = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        out.append(f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="1.4"{dash}/>')

        for (x, y), label in ((points[0], lstart), (points[-1], lend)):
            out.append(
                f'<text x="{x + 7}" y="{y - 6}" font-size="11" font-weight="600" '
                f'fill="{ACCENT}">{label}</text>')

    for name, (x, y, attrs) in ENTITIES.items():
        h = box_height(attrs)
        out.append(
            f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{h}" fill="#ffffff" '
            f'stroke="{INK}" stroke-width="1.6"/>')
        out.append(
            f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{HEADER_H}" fill="{INK}"/>')
        out.append(
            f'<text x="{x + 10}" y="{y + 18}" font-size="13" font-weight="700" '
            f'fill="#ffffff">{name}</text>')

        for i, (tag, attr) in enumerate(attrs):
            ty = y + HEADER_H + 12 + i * LINE_H
            colour = INK if tag.startswith("PK") else SOFT
            weight = "600" if tag.startswith("PK") else "400"
            deco = ' text-decoration="underline"' if tag.startswith("PK") else ""
            out.append(
                f'<text x="{x + 10}" y="{ty}" font-size="11.5" fill="{colour}" '
                f'font-weight="{weight}"{deco}>{attr}</text>')
            if tag:
                out.append(
                    f'<text x="{x + BOX_W - 10}" y="{ty}" font-size="9.5" '
                    f'text-anchor="end" fill="{ACCENT if tag == "D" else SOFT}">{tag}</text>')

    # legend
    lx, ly = 40, 772
    out.append(f'<text x="{lx}" y="{ly}" font-size="11" fill="{SOFT}">'
               f'PK = primary key &#160;&#160; FK = foreign key &#160;&#160; '
               f'D = derived, maintained by triggers &#160;&#160; '
               f'dashed = optional relationship</text>')

    out.append('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    svg = render()
    with open("report/er-diagram.svg", "w") as fh:
        fh.write(svg)
    print(f"wrote report/er-diagram.svg ({len(svg)} bytes)")
