"""Streaming reader and analytics for EdNet-KT1 interaction logs."""
from pathlib import Path
import csv
from collections import Counter, defaultdict

REQUIRED = {"timestamp", "solving_id", "question_id", "user_answer", "elapsed_time"}

def iter_interactions(data_dir, limit=None):
    """Yield KT1 rows without loading the full (~GB) dataset into memory."""
    root = Path(data_dir)
    files = sorted(root.glob("u*.csv"))
    seen = 0
    for file in files:
        with file.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not REQUIRED.issubset(set(reader.fieldnames or [])):
                continue
            for row in reader:
                try:
                    yield {"student": file.stem, "timestamp": int(row["timestamp"]),
                           "solving_id": int(row["solving_id"]), "question_id": row["question_id"],
                           "user_answer": row["user_answer"],
                           "elapsed_time_ms": max(0, int(row["elapsed_time"]))}
                    seen += 1
                    if limit is not None and seen >= limit:
                        return
                except (ValueError, TypeError):
                    continue

def dataset_stats(data_dir, sample_limit=250000):
    """Compute bounded-memory dataset statistics; sample_limit=None scans all rows."""
    students, questions = set(), set()
    answers, times = Counter(), []
    rows = 0
    for r in iter_interactions(data_dir, limit=sample_limit):
        rows += 1; students.add(r["student"]); questions.add(r["question_id"])
        answers[r["user_answer"]] += 1
        if r["elapsed_time_ms"] > 0: times.append(r["elapsed_time_ms"])
    times.sort()
    return {"rows_scanned": rows, "students_seen": len(students),
            "questions_seen": len(questions), "answer_distribution": dict(answers),
            "median_elapsed_seconds": round(times[len(times)//2]/1000, 2) if times else 0,
            "sampled": sample_limit is not None}

def learner_summary(data_dir, student_id, limit=100000):
    """Summarize a learner's KT1 sequence (KT1 has no correctness labels)."""
    count, total_ms, qset, answer_counts = 0, 0, set(), Counter()
    for r in iter_interactions(data_dir, limit=limit):
        if r["student"] != str(student_id): continue
        count += 1; total_ms += r["elapsed_time_ms"]
        qset.add(r["question_id"]); answer_counts[r["user_answer"]] += 1
    return {"student": str(student_id), "interactions": count, "unique_questions": len(qset),
            "total_time_minutes": round(total_ms/60000, 1), "answer_choices": dict(answer_counts)}
