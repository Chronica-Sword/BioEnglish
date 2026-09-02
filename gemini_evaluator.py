import os
import json
from typing import List
from pydantic import BaseModel, Field
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure the API key
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# ==========================================
# PYDANTIC SCHEMAS FOR STRUCTURED OUTPUT
# ==========================================

class Question(BaseModel):
    id: str = Field(description="Unique question id, e.g. q1, q2, q3, q4")
    question: str = Field(description="The reading comprehension question based on the text")
    options: List[str] = Field(description="List of exactly 4 multiple-choice options")
    answer: int = Field(description="0-indexed correct option index (0, 1, 2, or 3)")
    explanation: str = Field(description="Explanation of why this option is correct")

class Article(BaseModel):
    id: str = Field(description="Unique lower_case id for the article, e.g. b1_hydrogel_scaffolds")
    level: str = Field(description="Must be exactly the requested level: B1+, B2, B2+, or C1")
    title: str = Field(description="Academic and professional title of the article")
    summary: List[str] = Field(description="Exactly 4 key summary points of the article to reference")
    text: str = Field(description="The full biotechnology article text, between 1000 and 1500 words")
    questions: List[Question] = Field(description="Exactly 4 questions based on the article")
    writing_prompt: str = Field(description="An integrated essay prompt requiring analysis of the article")

class GrammarCorrection(BaseModel):
    original: str = Field(description="The original incorrect phrase or sentence in the essay")
    corrected: str = Field(description="The corrected version")
    explanation: str = Field(description="Brief explanation of the grammar rule or error")

class VocabularySuggestion(BaseModel):
    original_word: str = Field(description="The simple or incorrect word used by the user")
    suggested_word: str = Field(description="A higher-level academic C1-level synonym")
    context: str = Field(description="The context snippet where the word was used")
    explanation: str = Field(description="Why the suggested word fits better in an academic context")

class ScoreDetail(BaseModel):
    grammar: int = Field(description="Score from 1 to 10")
    vocabulary: int = Field(description="Score from 1 to 10")
    coherence: int = Field(description="Score from 1 to 10")
    task_achievement: int = Field(description="Score from 1 to 10")

class EssayEvaluation(BaseModel):
    score_toefl: int = Field(description="Overall TOEFL score from 0 to 30")
    score_ielts: float = Field(description="Overall IELTS score from 0.0 to 9.0 in 0.5 increments")
    scores: ScoreDetail = Field(description="Individual scoring criteria")
    overall_feedback: str = Field(description="A concise summary of strengths and core areas to improve (max 150 words)")
    grammar_corrections: List[GrammarCorrection] = Field(description="List of 5-6 key grammar corrections")
    vocabulary_suggestions: List[VocabularySuggestion] = Field(description="List of 4-5 high-impact vocabulary suggestions")
    coherence_tips: List[str] = Field(description="2-3 specific tips on coherence and flow")
    level_evaluation: str = Field(description="CEFR assessment and what is missing for C1 (max 50 words)")


# ==========================================
# EVALUATION & GENERATION LOGIC
# ==========================================

def evaluate_essay(essay_text, writing_prompt, article_title, article_level, article_summary_list):
    """
    Evaluates a user-submitted essay using Gemini API and returns a structured analysis.
    Uses response_schema to guarantee exact JSON keys.
    """
    if not api_key:
        return {
            "error": "Gemini API key is not configured. Please add your GEMINI_API_KEY to the .env file in the project folder.",
            "score_toefl": 18,
            "score_ielts": 6.0,
            "scores": {
                "grammar": 6,
                "vocabulary": 6,
                "coherence": 5,
                "task_achievement": 7
            },
            "overall_feedback": "This is a demonstration evaluation because the Gemini API key is missing. Add the API key in the settings to get a real evaluation of your writing.",
            "grammar_corrections": [
                {
                    "original": "The research show that...",
                    "corrected": "The research shows that...",
                    "explanation": "Subject-verb agreement: 'research' is singular, so the verb must be 'shows'."
                }
            ],
            "vocabulary_suggestions": [
                {
                    "original_word": "use",
                    "suggested_word": "utilize",
                    "context": "...to use CRISPR...",
                    "explanation": "'Utilize' is more formal and academic for discussing gene-editing tools."
                }
            ],
            "coherence_tips": [
                "Use linking words like 'furthermore' and 'consequently' to improve transitions."
            ],
            "level_evaluation": "Currently, this essay exhibits B1+ level writing. Configure your API key to get detailed analysis."
        }

    summary_str = "\n".join([f"- {s}" for s in article_summary_list])

    system_instruction = (
        "You are an expert English language examiner specializing in TOEFL iBT and IELTS Academic writing tests. "
        "Your task is to evaluate an integrated writing essay based on a biotechnology reading article. "
        "You must evaluate spelling, grammar, lexical resource, and coherence. "
        "Return the evaluation strictly matching the EssayEvaluation schema."
    )

    prompt = f"""
ARTICLE TITLE: {article_title}
ARTICLE LEVEL: {article_level}
ARTICLE SUMMARY (KEY POINTS):
{summary_str}

WRITING PROMPT:
{writing_prompt}

USER'S ESSAY:
---
{essay_text}
---

Please evaluate the essay according to the system instructions. Focus on providing feedback that helps a learner progress towards C1 level academic English.
"""

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": EssayEvaluation
            }
        )
        
        result = json.loads(response.text)
        return result
        
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return {
            "error": f"Failed to connect to Gemini API: {str(e)}."
        }

def generate_new_article(level, topic, prompt_override=None):
    """
    Generates a new biotechnology reading article at a specific level (B1+, B2, B2+, C1)
    along with reading questions and writing prompt using Gemini.
    Uses response_schema to guarantee exact JSON keys.
    """
    if not api_key:
        return None

    system_instruction = (
        "You are an expert curriculum developer for academic English (TOEFL/IELTS) and a science writer. "
        "Your task is to generate a comprehensive biotechnology reading article at a specified CEFR level. "
        "Return the output strictly matching the Article schema."
    )

    prompt = f"""
Generate a biotechnology article.
LEVEL: {level}
TOPIC: {topic}

Ensure the vocabulary and sentence structures strictly reflect the requested CEFR level ({level}).
- B1+ should have moderately complex compound sentences, clear explanations of key terms, and standard academic words.
- B2 should introduce more biotechnology concepts, varied sentence patterns, and strong transitional markers.
- B2+ should contain advanced vocabulary, passive voice constructs, and analyze scientific pros and cons.
- C1 should feature dense academic syntax, precise scientific jargon, and abstract arguments.

The text MUST be between 1000 and 1500 words to ensure it matches the study constraints.
"""

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": Article
            }
        )
        
        return json.loads(response.text)
    except Exception as e:
        print(f"Error generating article: {e}")
        return None

def generate_article_from_pdf(pdf_text):
    """
    Takes raw PDF text, analyzes it, and generates a structured Article JSON object
    matching the Article Pydantic schema using Gemini.
    """
    if not api_key:
        return None

    system_instruction = (
        "You are an expert curriculum developer for academic English (TOEFL/IELTS) and a science writer. "
        "Your task is to analyze a biotechnology PDF document text and convert it into a structured reading exercise. "
        "You must:\n"
        "1. Determine the CEFR level of the text (B1+, B2, B2+, or C1).\n"
        "2. Create a clean, readable version of the text (approx 800 to 1200 words) maintaining its original scientific rigor but optimized for a reading test.\n"
        "3. Generate exactly 4 reading comprehension questions with 4 options, answers, and explanations.\n"
        "4. Create 4 bullet summary points of the article.\n"
        "5. Create a writing prompt that asks the reader to write an integrated essay (max 750 words) analyzing the core ideas of the article.\n"
        "Return the output strictly matching the Article schema."
    )

    prompt = f"""
Here is the text extracted from the biotechnology PDF document:
---
{pdf_text}
---

Please process this text and return it in the Article schema. Generate a unique lowercase ID for it (e.g. b2_custom_uploaded_topic).
"""

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        # Limit token input length to prevent high costs
        truncated_prompt = prompt[:50000]
        
        response = model.generate_content(
            truncated_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": Article
            }
        )
        
        return json.loads(response.text)
    except Exception as e:
        print(f"Error generating article from PDF: {e}")
        return None

