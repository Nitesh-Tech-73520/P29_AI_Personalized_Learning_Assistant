"""Small-memory preprocessing utilities for EdNet KT1."""
from collections import defaultdict
from .loader import iter_interactions

def aggregate_students(data_dir, limit=None):
    stats = defaultdict(lambda: {"interactions": 0, "time_ms": 0, "questions": set()})
    for row in iter_interactions(data_dir, limit=limit):
        s = stats[row["student"]]
        s["interactions"] += 1; s["time_ms"] += row["elapsed_time_ms"]
        s["questions"].add(row["question_id"])
    return [{"student": key, "interactions": val["interactions"],
             "unique_questions": len(val["questions"]),
             "time_minutes": round(val["time_ms"]/60000, 2)}
            for key, val in stats.items()]

def question_popularity(data_dir, limit=None, top_n=20):
    counts = defaultdict(int)
    for row in iter_interactions(data_dir, limit=limit):
        counts[row["question_id"]] += 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
