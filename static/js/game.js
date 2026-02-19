let questions = [];
let currentQuestionIndex = 0;
let userAnswers = {};
let timerInterval;

document.addEventListener('DOMContentLoaded', () => {
    // Only run on quiz page
    if (document.getElementById('timer')) {
        startTimer(initialSeconds);
        fetchQuestions();
    }

    // Auto-refresh leaderboard
    if (document.getElementById('leaderboard-table')) {
        fetchLeaderboard();
        setInterval(fetchLeaderboard, 5000);
    }

    setupLightning();
});

function setupLightning() {
    // Inject flash overlay
    const flash = document.createElement('div');
    flash.className = 'lightning-flash';
    document.body.appendChild(flash);

    function triggerFlash() {
        // Random intensity: 70% Low, 30% High
        const isHigh = Math.random() > 0.7;
        const cls = isHigh ? 'flash-high' : 'flash-low';

        console.log(`⚡ Lightning: ${isHigh ? 'HIGH' : 'LOW'}`);

        flash.classList.add(cls);

        // Sync visual bolt with High intensity flash
        if (isHigh) {
            createBolt();
        }

        setTimeout(() => {
            flash.classList.remove(cls);
        }, 500);

        // Schedule next: Random between 3s and 10s
        const nextFlash = Math.random() * 7000 + 3000;
        setTimeout(triggerFlash, nextFlash);
    }

    // Start loop
    setTimeout(triggerFlash, 2000);
}

function createBolt() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "lightning-bolt");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("preserveAspectRatio", "none");

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");

    // Randomize start X (20% to 80% screen width)
    let startX = Math.random() * 60 + 20;
    let d = `M ${startX} 0`;
    let currentX = startX;
    let currentY = 0;

    // Create jagged path downwards
    while (currentY < 100) {
        currentY += Math.random() * 5 + 2; // Step down 2-7%
        currentX += (Math.random() - 0.5) * 10; // Jag left/right
        d += ` L ${currentX} ${currentY}`;
    }

    path.setAttribute("d", d);
    svg.appendChild(path);
    document.body.appendChild(svg);

    // Cleanup
    setTimeout(() => {
        svg.remove();
    }, 500);
}

function startTimer(seconds) {
    const timerDisplay = document.getElementById('timer');
    let remaining = seconds;

    function update() {
        if (remaining <= 0) {
            timerDisplay.innerText = "00:00";
            alert("Time's up! Submitting...");
            submitQuiz();
            clearInterval(timerInterval);
            return;
        }

        const m = Math.floor(remaining / 60);
        const s = remaining % 60;
        timerDisplay.innerText = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;

        // Critical visual warning
        if (remaining < 60) {
            timerDisplay.style.color = "red";
            timerDisplay.style.borderColor = "red";
        }

        remaining--;
    }

    update();
    timerInterval = setInterval(update, 1000);
}

async function fetchQuestions() {
    try {
        const response = await fetch('/api/questions');
        questions = await response.json();

        if (questions && questions.length > 0) {
            // Restore progress
            try {
                const saved = localStorage.getItem('pm_quiz_answers');
                if (saved) {
                    userAnswers = JSON.parse(saved);
                }
            } catch (e) {
                console.error("Failed to load saved state", e);
            }

            // Find first unattempted question
            let startIndex = 0;
            for (let i = 0; i < questions.length; i++) {
                if (!userAnswers[questions[i].id]) {
                    startIndex = i;
                    break;
                }
            }

            renderQuestion(startIndex);
        } else {
            console.error("Questions array is empty or null", questions);
            document.getElementById('question-text').innerText = "No questions found in database!";
        }
    } catch (e) {
        console.error("Failed to load questions", e);
        document.getElementById('question-text').innerText = "Error loading questions.";
    }
}

function renderQuestion(index) {
    if (index < 0 || index >= questions.length) return;

    // Save current answer before switching
    saveCurrentAnswer();

    currentQuestionIndex = index;
    const q = questions[index];

    document.getElementById('q-number').innerText = index + 1;
    document.getElementById('question-text').innerText = q.content_text || "";
    document.getElementById('q-points').innerText = q.points;

    const diffEl = document.getElementById('q-difficulty');
    diffEl.innerText = q.difficulty;

    // Reset classes
    diffEl.classList.remove('text-easy', 'text-medium', 'text-hard');

    if (q.difficulty === 'Easy') {
        diffEl.classList.add('text-easy');
    } else if (q.difficulty === 'Medium') {
        diffEl.classList.add('text-medium');
    } else if (q.difficulty === 'Hard') {
        diffEl.classList.add('text-hard');
    }

    const img = document.getElementById('question-image');
    if (q.content_image) {
        img.src = q.content_image;
        img.style.display = "block";
    } else {
        img.style.display = "none";
    }

    // Input Area
    const inputContainer = document.getElementById('answer-input-container');
    inputContainer.innerHTML = ''; // Clear previous input

    if (q.options) {
        // MCQ Mode
        const options = q.options.split('|');
        const container = document.createElement('div');
        container.className = 'mcq-grid';

        options.forEach(opt => {
            const trimmed = opt.trim();
            const label = document.createElement('label');
            label.className = 'mcq-card';

            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = 'mcq_option';
            radio.value = trimmed;

            // Restore selection
            if (userAnswers[q.id] === trimmed) {
                radio.checked = true;
            }

            const span = document.createElement('span');
            span.innerText = trimmed;

            label.appendChild(radio);
            label.appendChild(span);
            container.appendChild(label);
        });
        inputContainer.appendChild(container);
    } else {
        // Text Mode
        const input = document.createElement('input');
        input.type = 'text';
        input.id = 'answer-input';
        input.placeholder = 'Your Answer...';
        input.style.textAlign = 'center';
        input.value = userAnswers[q.id] || "";
        inputContainer.appendChild(input);

        // Auto-focus text input
        setTimeout(() => input.focus(), 100);
    }

    // Button state
    document.getElementById('prev-btn').disabled = index === 0;
    document.getElementById('next-btn').innerText = index === questions.length - 1 ? "Finish" : "Next >";
}

function saveCurrentAnswer() {
    if (questions.length === 0) return;
    const q = questions[currentQuestionIndex];

    if (q.options) {
        const selected = document.querySelector('input[name="mcq_option"]:checked');
        if (selected) {
            userAnswers[q.id] = selected.value;
        }
    } else {
        const input = document.getElementById('answer-input');
        if (input) {
            userAnswers[q.id] = input.value;
        }
    }

    // Persist to handle reloads
    localStorage.setItem('pm_quiz_answers', JSON.stringify(userAnswers));
}

function nextQuestion() {
    if (currentQuestionIndex < questions.length - 1) {
        renderQuestion(currentQuestionIndex + 1);
    } else {
        // Last question: Finish
        submitQuiz();
    }
}

function prevQuestion() {
    if (currentQuestionIndex > 0) {
        renderQuestion(currentQuestionIndex - 1);
    }
}

async function submitQuiz() {
    saveCurrentAnswer(); // Ensure last answer is saved

    // Confirmation if manually submitting (not timeout)
    if (document.getElementById('timer').innerText !== "00:00" && !confirm("Are you sure you want to finish the quiz?")) {
        return;
    }

    try {
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userAnswers)
        });

        const result = await response.json();
        if (result.redirect) {
            // Clear storage on success
            localStorage.removeItem('pm_quiz_answers');
            window.location.href = result.redirect;
        }
    } catch (e) {
        alert("Submission failed! Try again.");
    }
}

async function fetchLeaderboard() {
    try {
        const response = await fetch('/api/leaderboard');
        const data = await response.json();
        const tbody = document.querySelector('#leaderboard-table tbody');
        tbody.innerHTML = '';

        data.forEach((team, index) => {
            const row = `<tr>
                <td>${index + 1}</td>
                <td>${team.name}</td>
                <td>${team.score}</td>
                <td>${team.time_taken}</td>
            </tr>`;
            tbody.innerHTML += row;
        });
    } catch (e) { console.error(e); }
}

// Feedback Modal Logic
function openFeedback() {
    const modal = document.getElementById('feedback-modal');
    modal.style.display = 'flex';
    document.getElementById('feedback-text').focus();
}

function closeFeedback() {
    document.getElementById('feedback-modal').style.display = 'none';
}

// Close on outside click
window.onclick = function (event) {
    const modal = document.getElementById('feedback-modal');
    if (event.target == modal) {
        closeFeedback();
    }
}

async function submitFeedback() {
    const text = document.getElementById('feedback-text').value;
    if (!text.trim()) return;

    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: text })
        });

        const result = await response.json();
        if (result.success) {
            alert("Thanks for your thoughts! 🧠");
            document.getElementById('feedback-text').value = "";
            closeFeedback();
        }
    } catch (e) {
        alert("Failed to send feedback.");
    }
}
