from pydantic import BaseModel
from typing import Dict, List


class DiagnosticTestSubmission(BaseModel):
    user_id: int
    # JSON nesnelerinde anahtarlar her zaman string'dir; soru id'leri string olarak gelir.
    answers: Dict[str, str]


class DiagnosticResult(BaseModel):
    total_questions: int
    correct_answers: int
    estimated_score: float
    weak_categories: List[str]


class AIQuestionFormat(BaseModel):
    question_text: str
    options: Dict[str, str]   # {"A": "...", "B": "...", ...}
    correct_option: str       # Sadece "A", "B", "C", "D" veya "E"
    category: str             # "vocabulary" veya "grammar"
