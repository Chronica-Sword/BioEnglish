import os
import json
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'biotech_learning.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create articles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            level TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,  -- stored as JSON string
            text TEXT NOT NULL,
            questions TEXT NOT NULL, -- stored as JSON string
            writing_prompt TEXT NOT NULL
        )
    ''')
    
    # Create essays table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS essays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id TEXT NOT NULL,
            date_submitted TEXT NOT NULL,
            essay_text TEXT NOT NULL,
            score_toefl INTEGER NOT NULL,
            score_ielts REAL NOT NULL,
            grammar_score INTEGER NOT NULL,
            vocabulary_score INTEGER NOT NULL,
            coherence_score INTEGER NOT NULL,
            task_score INTEGER NOT NULL,
            feedback_json TEXT NOT NULL, -- stored as JSON string
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
    ''')
    
    # Create vocabulary table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vocabulary (
            word TEXT PRIMARY KEY,
            definition TEXT NOT NULL,
            example TEXT,
            date_added TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    
    # Seed articles if empty
    cursor.execute("SELECT COUNT(*) FROM articles")
    if cursor.fetchone()[0] == 0:
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'articles_seed.json')
        if os.path.exists(seed_path):
            with open(seed_path, 'r', encoding='utf-8') as f:
                articles = json.load(f)
                for a in articles:
                    cursor.execute('''
                        INSERT INTO articles (id, level, title, summary, text, questions, writing_prompt)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        a['id'],
                        a['level'],
                        a['title'],
                        json.dumps(a['summary']),
                        a['text'],
                        json.dumps(a['questions']),
                        a['writing_prompt']
                    ))
            conn.commit()
            print("Database successfully seeded with initial articles.")
            
    conn.close()

def get_all_articles():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, level, title FROM articles")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_article(article_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        article = dict(row)
        article['summary'] = json.loads(article['summary'])
        article['questions'] = json.loads(article['questions'])
        return article
    return None

def add_essay(article_id, essay_text, scores, feedback):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO essays (
            article_id, date_submitted, essay_text, score_toefl, score_ielts,
            grammar_score, vocabulary_score, coherence_score, task_score, feedback_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        article_id,
        date_str,
        essay_text,
        scores.get('toefl', 0),
        scores.get('ielts', 0.0),
        scores.get('grammar', 0),
        scores.get('vocabulary', 0),
        scores.get('coherence', 0),
        scores.get('task', 0),
        json.dumps(feedback)
    ))
    conn.commit()
    essay_id = cursor.lastrowid
    conn.close()
    return essay_id

def get_essay_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.*, a.title as article_title, a.level as article_level
        FROM essays e
        JOIN articles a ON e.article_id = a.id
        ORDER BY e.date_submitted DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    essays = []
    for row in rows:
        d = dict(row)
        d['feedback_json'] = json.loads(d['feedback_json'])
        essays.append(d)
    return essays

def get_essay(essay_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.*, a.title as article_title, a.level as article_level, a.writing_prompt
        FROM essays e
        JOIN articles a ON e.article_id = a.id
        WHERE e.id = ?
    ''', (essay_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['feedback_json'] = json.loads(d['feedback_json'])
        return d
    return None

def add_word(word, definition, example=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO vocabulary (word, definition, example, date_added)
            VALUES (?, ?, ?, ?)
        ''', (word.strip().lower(), definition, example, date_str))
        conn.commit()
        success = True
    except Exception:
        success = False
    finally:
        conn.close()
    return success

def get_vocabulary():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vocabulary ORDER BY date_added DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_word(word):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocabulary WHERE word = ?", (word.lower(),))
    conn.commit()
    conn.close()

def get_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total articles read (articles with at least one essay submitted, or total essays count)
    cursor.execute("SELECT COUNT(DISTINCT article_id) FROM essays")
    articles_practiced = cursor.fetchone()[0]
    
    # Total essays submitted
    cursor.execute("SELECT COUNT(*) FROM essays")
    total_essays = cursor.fetchone()[0]
    
    # Total vocabulary words saved
    cursor.execute("SELECT COUNT(*) FROM vocabulary")
    vocab_count = cursor.fetchone()[0]
    
    # Average TOEFL score
    cursor.execute("SELECT AVG(score_toefl) FROM essays")
    avg_toefl = cursor.fetchone()[0]
    avg_toefl = round(avg_toefl, 1) if avg_toefl is not None else 0
    
    # Average IELTS score
    cursor.execute("SELECT AVG(score_ielts) FROM essays")
    avg_ielts = cursor.fetchone()[0]
    avg_ielts = round(avg_ielts, 1) if avg_ielts is not None else 0.0
    
    conn.close()
    
    return {
        'articles_practiced': articles_practiced,
        'total_essays': total_essays,
        'vocab_count': vocab_count,
        'avg_toefl': avg_toefl,
        'avg_ielts': avg_ielts
    }
