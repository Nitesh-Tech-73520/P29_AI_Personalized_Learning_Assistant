"""Build a transparent KT1 engagement baseline (not a correctness/mastery model).

KT1 contains answer choices and elapsed time but not correctness labels. This
module therefore reports engagement/question-frequency features only.
"""
from .preprocess import aggregate_students, question_popularity

def build_baseline(data_dir, limit=250000):
    learners = aggregate_students(data_dir, limit=limit)
    popular = question_popularity(data_dir, limit=limit, top_n=15)
    learners.sort(key=lambda x: x["interactions"], reverse=True)
    return {"rows_limit": limit, "learner_count": len(learners),
            "most_active_learners": learners[:10],
            "popular_questions": popular,
            "model_note": "KT1 engagement baseline; correctness/mastery prediction requires KT2 labels."}

if __name__ == "__main__":
    from pathlib import Path
    data = Path(__file__).resolve().parents[1] / "data" / "EdNet" / "KT1"
    print(build_baseline(data))
