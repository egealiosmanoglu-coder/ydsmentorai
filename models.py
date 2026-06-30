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


class UserRegister(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    solved_count: int
    correct_count: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AnswerSubmission(BaseModel):
    question_id: int
    selected_option: str
