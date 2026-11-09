import re
from collections import Counter

STOP = set("the a an and or but is are was were be been being to of in on for with as by from that this these those it its into than then also can may will should would could".split())

def _tokens(text):
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}", text) if w.lower() not in STOP]

def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 35]

def answer_question(db, student_id, question):
    materials = db.fetchall(
        """SELECT m.title, m.content, t.topic_name, c.course_name
           FROM learning_materials m JOIN topics t ON m.topic_id=t.topic_id
           JOIN courses c ON t.course_id=c.course_id"""
    )
    qwords = set(_tokens(question))
    ranked = []
    for material in materials:
        sentences = _sentences(material["content"] or "")
        for sentence in sentences:
            words = set(_tokens(sentence))
            overlap = len(qwords & words)
            if overlap:
                ranked.append((overlap / max(1, len(qwords)), sentence, material))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if not ranked:
        if not materials:
            return ("I don't have any learning materials to search yet. Open Learning Materials and upload a PDF or TXT file first.", [])
        return ("I couldn't find a relevant answer in the uploaded learning materials. Try asking with terms from your course notes.", [])
    selected = ranked[:3]
    answer = "Here is what I found in your learning materials:\n\n" + "\n\n".join(f"• {item[1]}" for item in selected)
    sources = list(dict.fromkeys(f'{x[2]["title"]} — {x[2]["topic_name"]}' for x in selected))
    answer += "\n\nStudy tip: Try explaining this concept in your own words, then test yourself with a quiz."
    return answer, sources

def build_quiz(db, topic_id, count=5):
    rows = db.fetchall("SELECT title, content FROM learning_materials WHERE topic_id=%s", (topic_id,))
    text = " ".join(r["content"] or "" for r in rows)
    sentences = [s for s in _sentences(text) if len(_tokens(s)) >= 5]
    if len(sentences) < 2:
        return []
    questions = []
    for sentence in sentences[:count]:
        words = [w for w in re.findall(r"\b[A-Za-z][A-Za-z0-9_+-]{3,}\b", sentence) if w.lower() not in STOP]
        if not words:
            continue
        answer = max(words, key=len)
        prompt = re.sub(re.escape(answer), "________", sentence, count=1, flags=re.IGNORECASE)
        distractors = list(dict.fromkeys([w for s in sentences if s != sentence for w in re.findall(r"\b[A-Za-z][A-Za-z0-9_+-]{3,}\b", s) if w.lower() not in STOP and w.lower() != answer.lower()]))
        random.shuffle(distractors)
        options = [answer] + distractors[:3]
        while len(options) < 4:
            options.append("None of these")
        random.shuffle(options)
        questions.append({"question": f"Complete the statement: {prompt}", "options": options, "answer": options.index(answer)})
    return questions

def recommend_topics(db, student_id):
    topics = db.fetchall(
        """SELECT t.topic_id, t.topic_name, c.course_name,
           AVG(q.score) AS avg_score, COUNT(q.attempt_id) AS attempts
           FROM topics t JOIN courses c ON t.course_id=c.course_id
           LEFT JOIN quiz_attempts q ON q.topic_id=t.topic_id AND q.student_id=%s
           GROUP BY t.topic_id, t.topic_name, c.course_name
           ORDER BY CASE WHEN COUNT(q.attempt_id)=0 THEN 0 ELSE AVG(q.score) END ASC
           LIMIT 5""", (student_id,)
    )
    result = []
    for t in topics:
        avg = float(t["avg_score"]) if t["avg_score"] is not None else None
        if avg is None:
            reason = "Not attempted yet — start here to establish your level."
        elif avg < 60:
            reason = f"Your average score is {avg:.0f}%. Revise this topic and try another quiz."
        elif avg < 80:
            reason = f"Your average score is {avg:.0f}%. A little more practice will strengthen this topic."
        else:
            reason = f"Your average score is {avg:.0f}%. Keep your skills fresh with revision."
        result.append({**t, "reason": reason})
    return result
