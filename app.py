import os
import json
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv

import db_manager
import gemini_evaluator
from pypdf import PdfReader

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize database on startup
db_manager.init_db()

@app.context_processor
def inject_api_status():
    """Injects whether the Gemini API key is configured in all templates."""
    key = os.getenv("GEMINI_API_KEY")
    return {
        'api_key_configured': key,
        'api_key_status': True if key else False
    }

@app.route('/')
def index():
    articles = db_manager.get_all_articles()
    stats = db_manager.get_statistics()
    vocab = db_manager.get_vocabulary()
    history = db_manager.get_essay_history()
    
    return render_template('index.html', 
                           articles=articles, 
                           stats=stats, 
                           vocab=vocab[:10], # Show top 10 in sidebar
                           history=history,
                           active_page='dashboard')

@app.route('/reader/<article_id>')
def reader(article_id):
    article = db_manager.get_article(article_id)
    if not article:
        return "Article not found", 404
    return render_template('reader.html', article=article, active_page='dashboard')

@app.route('/writer/<article_id>')
def writer(article_id):
    article = db_manager.get_article(article_id)
    if not article:
        return "Article not found", 404
    return render_template('writer.html', article=article, active_page='dashboard')

@app.route('/history')
def history():
    essays = db_manager.get_essay_history()
    return render_template('history.html', essays=essays, active_page='history')

@app.route('/essay/review/<essay_id>')
def essay_review(essay_id):
    essay = db_manager.get_essay(essay_id)
    if not essay:
        return "Evaluation report not found", 404
    return render_template('review.html', essay=essay, active_page='history')

# ==========================================
# API ENDPOINTS
# ==========================================

@app.route('/api/vocab/add', methods=['POST'])
def add_vocab():
    data = request.json
    word = data.get('word')
    definition = data.get('definition')
    example = data.get('example')
    
    if not word or not definition:
        return jsonify({'success': False, 'error': 'Missing word or definition'}), 400
        
    success = db_manager.add_word(word, definition, example)
    return jsonify({'success': success})

@app.route('/api/vocab/delete', methods=['POST'])
def delete_vocab():
    data = request.json
    word = data.get('word')
    if not word:
        return jsonify({'success': False, 'error': 'Missing word'}), 400
    db_manager.delete_word(word)
    return jsonify({'success': True})

@app.route('/api/essay/submit', methods=['POST'])
def submit_essay():
    data = request.json
    article_id = data.get('article_id')
    essay_text = data.get('essay_text')
    
    if not article_id or not essay_text:
        return jsonify({'success': False, 'error': 'Missing article ID or essay text'}), 400
        
    article = db_manager.get_article(article_id)
    if not article:
        return jsonify({'success': False, 'error': 'Article not found'}), 404
        
    # Evaluate using Gemini
    feedback = gemini_evaluator.evaluate_essay(
        essay_text=essay_text,
        writing_prompt=article['writing_prompt'],
        article_title=article['title'],
        article_level=article['level'],
        article_summary_list=article['summary']
    )
    
    if 'error' in feedback and not feedback.get('score_toefl'):
        # Only error without a fallback mock
        return jsonify({'success': False, 'error': feedback['error']}), 500
        
    # Save to database
    scores = {
        'toefl': feedback.get('score_toefl', 0),
        'ielts': feedback.get('score_ielts', 0.0),
        'grammar': feedback.get('scores', {}).get('grammar', 0),
        'vocabulary': feedback.get('scores', {}).get('vocabulary', 0),
        'coherence': feedback.get('scores', {}).get('coherence', 0),
        'task': feedback.get('scores', {}).get('task_achievement', 0)
    }
    
    essay_id = db_manager.add_essay(
        article_id=article_id,
        essay_text=essay_text,
        scores=scores,
        feedback=feedback
    )
    
    return jsonify({'success': True, 'essay_id': essay_id})

@app.route('/api/settings/save', methods=['POST'])
def save_settings():
    data = request.json
    api_key = data.get('api_key')
    
    # Write to .env file locally
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f"GEMINI_API_KEY={api_key}\n")
        
    # Update current process variables
    os.environ['GEMINI_API_KEY'] = api_key
    
    # Reconfigure Gemini SDK
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gemini_evaluator.api_key = api_key
    
    return jsonify({'success': True})

@app.route('/api/articles/generate', methods=['POST'])
def generate_article():
    data = request.json
    level = data.get('level')
    topic = data.get('topic')
    
    if not level or not topic:
        return jsonify({'success': False, 'error': 'Missing level or topic'}), 400
        
    # Generate new article using Gemini
    new_article = gemini_evaluator.generate_new_article(level, topic)
    if not new_article:
        return jsonify({'success': False, 'error': 'Could not generate article. Please verify your API Key.'}), 500
        
    # Save to database
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO articles (id, level, title, summary, text, questions, writing_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_article['id'],
            new_article['level'],
            new_article['title'],
            json.dumps(new_article['summary']),
            new_article['text'],
            json.dumps(new_article['questions']),
            new_article['writing_prompt']
        ))
        conn.commit()
        success = True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error saving generated article: {e}")
        print(f"Generated article keys: {list(new_article.keys()) if new_article else 'None'}")
        success = False
    finally:
        conn.close()
        
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to save generated article to database.'}), 500

@app.route('/api/articles/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
        
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'File is not a PDF'}), 400
        
    try:
        # Read the PDF and extract text
        reader = PdfReader(file)
        text_content = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_content += text + "\n"
                
        if len(text_content.strip()) < 100:
            return jsonify({'success': False, 'error': 'Could not extract enough text from the PDF. Make sure it is not an image-only PDF.'}), 400
            
        # Call Gemini to process the text
        new_article = gemini_evaluator.generate_article_from_pdf(text_content)
        if not new_article:
            return jsonify({'success': False, 'error': 'AI processing failed. Verify your Gemini API Key.'}), 500
            
        # Save to database
        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO articles (id, level, title, summary, text, questions, writing_prompt)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_article['id'],
                new_article['level'],
                new_article['title'],
                json.dumps(new_article['summary']),
                new_article['text'],
                json.dumps(new_article['questions']),
                new_article['writing_prompt']
            ))
            conn.commit()
            success = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error saving generated article: {e}")
            success = False
        finally:
            conn.close()
            
        if success:
            return jsonify({'success': True, 'article_id': new_article['id']})
        else:
            return jsonify({'success': False, 'error': 'Failed to save generated article to database.'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'PDF processing failed: {str(e)}'}), 500

if __name__ == '__main__':
    # Start the Flask app locally on port 5000
    app.run(debug=True, host='127.0.0.1', port=5000)
