document.addEventListener('DOMContentLoaded', () => {
    initReader();
    initWriter();
    initSettings();
});

// ==========================================
// 1. READER INTERFACE LOGIC
// ==========================================
function initReader() {
    const readingText = document.getElementById('reading-text');
    if (!readingText) return;

    // A. Tokenize Text into Clickable Words
    // We want to wrap every word in a span while preserving paragraph structure
    const paragraphs = readingText.getElementsByTagName('p');
    for (let p of paragraphs) {
        const text = p.innerHTML;
        // Split by whitespace but keep HTML tags if any (none in our seed data, but safe)
        const words = text.split(/(\s+)/);
        const wrappedWords = words.map(chunk => {
            if (chunk.trim() === '') return chunk;
            // Clean word from punctuation for dictionary lookup
            const cleaned = chunk.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()?"']/g, "").toLowerCase();
            if (cleaned === '') return chunk;
            
            // Keep punctuation in display, but attach clean word as data attribute
            return `<span class="word" data-word="${cleaned}">${chunk}</span>`;
        });
        p.innerHTML = wrappedWords.join('');
    }

    // B. Setup Word Click Listeners
    readingText.addEventListener('click', (e) => {
        if (e.target.classList.contains('word')) {
            const word = e.target.getAttribute('data-word');
            lookupWord(word);
        }
    });

    // C. Text Size Controls
    let currentFontSize = 1.1; // rem
    document.getElementById('btn-zoom-in')?.addEventListener('click', () => {
        currentFontSize += 0.1;
        readingText.style.fontSize = `${currentFontSize}rem`;
    });
    document.getElementById('btn-zoom-out')?.addEventListener('click', () => {
        if (currentFontSize > 0.9) {
            currentFontSize -= 0.1;
            readingText.style.fontSize = `${currentFontSize}rem`;
        }
    });

    // D. Comprehension Questions Grading
    initQuiz();
}

// Word lookup using Free Dictionary API (0 token cost)
let currentDefinition = "";
let currentExample = "";

function lookupWord(word) {
    const modal = document.getElementById('dict-modal');
    const title = document.getElementById('dict-title');
    const body = document.getElementById('dict-body');
    const saveBtn = document.getElementById('btn-save-vocab');
    
    if (!modal) return;

    title.innerText = word;
    body.innerHTML = '<p class="dict-pos">Searching...</p>';
    modal.classList.add('active');
    
    saveBtn.style.display = 'none';

    fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${word}`)
        .then(response => {
            if (!response.ok) throw new Error('Word not found');
            return response.json();
        })
        .then(data => {
            const entry = data[0];
            const meaning = entry.meanings[0];
            const definitionObj = meaning.definitions[0];
            
            const partOfSpeech = meaning.partOfSpeech;
            currentDefinition = definitionObj.definition;
            currentExample = definitionObj.example || "No example sentence available.";

            body.innerHTML = `
                <p class="dict-pos">${partOfSpeech}</p>
                <p class="dict-def">${currentDefinition}</p>
                ${definitionObj.example ? `<p class="dict-example">"${currentExample}"</p>` : ''}
            `;
            
            saveBtn.style.display = 'block';
        })
        .catch(err => {
            body.innerHTML = `
                <p class="dict-pos" style="color: var(--color-error)">No definition found.</p>
                <p class="dict-def">Could not retrieve information for "${word}".</p>
            `;
        });
}

function closeDict() {
    document.getElementById('dict-modal')?.classList.remove('active');
}

function saveWordToVocab() {
    const word = document.getElementById('dict-title').innerText;
    if (!word) return;

    fetch('/api/vocab/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            word: word,
            definition: currentDefinition,
            example: currentExample
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Show brief visual confirmation
            const saveBtn = document.getElementById('btn-save-vocab');
            const originalText = saveBtn.innerHTML;
            saveBtn.innerHTML = 'Saved! ✓';
            saveBtn.style.backgroundColor = 'var(--color-success)';
            setTimeout(() => {
                saveBtn.innerHTML = originalText;
                saveBtn.style.backgroundColor = '';
                closeDict();
            }, 1000);
        }
    });
}

// Vocabulary Word Deletion
function deleteVocabWord(word) {
    if (!confirm(`Remove "${word}" from your vocabulary bank?`)) return;

    fetch('/api/vocab/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word: word })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            location.reload();
        }
    });
}

// Comprehension Quiz Grading
function initQuiz() {
    const quizPane = document.getElementById('quiz-pane');
    if (!quizPane) return;

    const questions = quizPane.querySelectorAll('.question-container');
    const submitBtn = document.getElementById('btn-submit-quiz');
    const resultBox = document.getElementById('quiz-result');
    const selectedAnswers = {};

    questions.forEach(q => {
        const qId = q.getAttribute('data-q-id');
        const optionBtns = q.querySelectorAll('.option-btn');
        
        optionBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove selected class from sibling buttons
                optionBtns.forEach(b => b.classList.remove('selected'));
                // Select this one
                btn.classList.add('selected');
                selectedAnswers[qId] = parseInt(btn.getAttribute('data-index'));
            });
        });
    });

    submitBtn?.addEventListener('click', () => {
        let correctCount = 0;
        const total = questions.length;

        questions.forEach(q => {
            const qId = q.getAttribute('data-q-id');
            const correctIndex = parseInt(q.getAttribute('data-correct'));
            const optionBtns = q.querySelectorAll('.option-btn');
            const explanation = q.querySelector('.explanation-box');

            const userAnswer = selectedAnswers[qId];

            optionBtns.forEach(btn => {
                const btnIndex = parseInt(btn.getAttribute('data-index'));
                btn.classList.remove('selected', 'correct', 'incorrect');

                if (btnIndex === correctIndex) {
                    btn.classList.add('correct'); // Highlight correct option
                }
                
                if (btnIndex === userAnswer && btnIndex !== correctIndex) {
                    btn.classList.add('incorrect'); // Highlight incorrect user selection
                }
            });

            if (userAnswer === correctIndex) {
                correctCount++;
            }

            if (explanation) {
                explanation.style.display = 'block'; // Show explanation
            }
        });

        if (resultBox) {
            resultBox.innerHTML = `You scored <strong>${correctCount} / ${total}</strong>. Check explanations below!`;
            resultBox.style.display = 'block';
            resultBox.className = 'explanation-box';
            resultBox.style.borderLeftColor = correctCount === total ? 'var(--color-success)' : 'var(--color-secondary)';
        }

        // Disable options after submission
        quizPane.querySelectorAll('.option-btn').forEach(btn => btn.style.pointerEvents = 'none');
        submitBtn.style.display = 'none';
        
        // Show proceed to writing button
        document.getElementById('btn-go-writing').style.display = 'inline-flex';
    });
}

// ==========================================
// 2. WRITER INTERFACE LOGIC
// ==========================================
function initWriter() {
    const editor = document.getElementById('essay-editor');
    if (!editor) return;

    const wordCountSpan = document.getElementById('word-count');
    const wordWarning = document.getElementById('word-warning');
    const submitBtn = document.getElementById('btn-submit-essay');
    const overlay = document.getElementById('loading-overlay');
    const timerSpan = document.getElementById('writing-timer');

    // A. Word Counter (Max 750 words)
    editor.addEventListener('input', () => {
        const text = editor.value.trim();
        const wordCount = text === "" ? 0 : text.split(/\s+/).length;
        wordCountSpan.innerText = wordCount;

        if (wordCount > 750) {
            wordWarning.style.color = 'var(--color-error)';
            wordWarning.style.fontWeight = 'bold';
            editor.style.borderColor = 'var(--color-error)';
            submitBtn.disabled = true;
        } else if (wordCount > 700) {
            wordWarning.style.color = 'var(--color-accent)';
            editor.style.borderColor = 'var(--color-accent)';
            submitBtn.disabled = false;
        } else {
            wordWarning.style.color = '';
            editor.style.borderColor = '';
            submitBtn.disabled = false;
        }
    });

    // B. Writing Timer (30 minutes target)
    let seconds = 30 * 60; // 30 mins
    const interval = setInterval(() => {
        seconds--;
        if (seconds <= 0) {
            clearInterval(interval);
            timerSpan.innerText = "Time's up!";
            timerSpan.style.color = 'var(--color-error)';
        } else {
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            timerSpan.innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
    }, 1000);

    // C. Submit Essay for AI Review
    submitBtn.addEventListener('click', () => {
        const text = editor.value.trim();
        const wordCount = text === "" ? 0 : text.split(/\s+/).length;
        
        if (wordCount < 100) {
            alert('Your essay is too short. Please write at least 100 words to receive an evaluation.');
            return;
        }

        const articleId = document.getElementById('article-id').value;
        
        // Show Loading Overlay
        overlay.classList.add('active');
        cycleLoadingQuotes();
        clearInterval(interval);

        fetch('/api/essay/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                article_id: articleId,
                essay_text: text
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Redirect to review page
                window.location.href = `/essay/review/${data.essay_id}`;
            } else {
                overlay.classList.remove('active');
                alert(`Error evaluating essay: ${data.error || 'Unknown error'}`);
            }
        })
        .catch(err => {
            overlay.classList.remove('active');
            alert('An error occurred during submission. Please check your internet connection and API key configuration.');
        });
    });
}

// Motivational/Biotech related loading quotes to display during evaluation
const quotes = [
    "Gemini is analyzing your essay structure...",
    "Grading spelling and grammatical cohesion...",
    "Scanning for C1 level lexical alternatives...",
    "Biotechnology is the code of life, you are writing the code of your career.",
    "Evaluating argument flow and integrated text linkages...",
    "Finalizing TOEFL / IELTS feedback scoring grids..."
];
let quoteIndex = 0;
function cycleLoadingQuotes() {
    const textEl = document.getElementById('loading-quote');
    if (!textEl) return;
    textEl.innerText = quotes[quoteIndex];
    quoteIndex = (quoteIndex + 1) % quotes.length;
    setTimeout(() => {
        if (document.getElementById('loading-overlay').classList.contains('active')) {
            cycleLoadingQuotes();
        }
    }, 3000);
}

// ==========================================
// 3. SETTINGS & CORE MODAL LOGIC
// ==========================================
function initSettings() {
    const settingsBtn = document.getElementById('nav-settings');
    const modal = document.getElementById('settings-modal');
    const overlay = document.getElementById('settings-overlay');
    const saveBtn = document.getElementById('btn-save-settings');
    const closeBtn = document.getElementById('btn-close-settings');

    if (!settingsBtn || !modal) return;

    const toggle = () => {
        modal.classList.toggle('active');
        overlay.classList.toggle('active');
    };

    settingsBtn.addEventListener('click', (e) => { e.preventDefault(); toggle(); });
    overlay.addEventListener('click', toggle);
    closeBtn.addEventListener('click', toggle);

    saveBtn.addEventListener('click', () => {
        const apiKey = document.getElementById('settings-api-key').value.trim();
        fetch('/api/settings/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('API Key saved successfully!');
                toggle();
                location.reload();
            } else {
                alert('Failed to save API key.');
            }
        });
    });

    // Generate Article Trigger
    const genBtn = document.getElementById('btn-generate-article');
    if (genBtn) {
        genBtn.addEventListener('click', () => {
            const level = document.getElementById('gen-level').value;
            const topic = document.getElementById('gen-topic').value.trim();

            if (!topic) {
                alert('Please specify a topic (e.g. \"CRISPR in Agriculture\", \"Biofuels\").');
                return;
            }

            genBtn.innerText = 'Generating (Take ~30s)...';
            genBtn.disabled = true;

            fetch('/api/articles/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level: level, topic: topic })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('New biotechnology article successfully generated and saved!');
                    toggle();
                    window.location.reload();
                } else {
                    alert(`Generation failed: ${data.error}. Verify your Gemini API key is configured.`);
                    genBtn.innerText = 'Generate Article';
                    genBtn.disabled = false;
                }
            })
            .catch(err => {
                alert('An error occurred during article generation.');
                genBtn.innerText = 'Generate Article';
                genBtn.disabled = false;
            });
        });
    }

    // PDF Upload Trigger
    const uploadBtn = document.getElementById('btn-upload-pdf');
    const fileInput = document.getElementById('pdf-file-input');
    
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => {
            const file = fileInput.files[0];
            if (!file) {
                alert('Please select a PDF file first.');
                return;
            }
            
            const formData = new FormData();
            formData.append('pdf_file', file);
            
            uploadBtn.innerText = 'Uploading & Processing (Take ~30-45s)...';
            uploadBtn.disabled = true;
            
            fetch('/api/articles/upload_pdf', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('PDF successfully parsed and reading exercise created!');
                    toggle(); // Close settings modal
                    window.location.href = `/reader/${data.article_id}`; // Redirect to reader
                } else {
                    alert(`Processing failed: ${data.error}. Make sure your Gemini API key is configured.`);
                    uploadBtn.innerText = 'Upload & Process PDF';
                    uploadBtn.disabled = false;
                }
            })
            .catch(err => {
                alert('An error occurred during PDF upload and processing.');
                uploadBtn.innerText = 'Upload & Process PDF';
                uploadBtn.disabled = false;
            });
        });
    }
}
