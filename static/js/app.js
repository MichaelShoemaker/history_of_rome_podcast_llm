// History of Rome AI Assistant - Frontend JavaScript

class HistoryOfRomeApp {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.checkSystemStatus();
        this.loadExamples();
    }

    initializeElements() {
        this.questionInput = document.getElementById('questionInput');
        this.askButton = document.getElementById('askButton');
        this.contextLimit = document.getElementById('contextLimit');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.examplesSection = document.getElementById('examplesSection');
        this.examplesGrid = document.getElementById('examplesGrid');
        this.responseSection = document.getElementById('responseSection');
        this.loadingSection = document.getElementById('loadingSection');
        this.answerContent = document.getElementById('answerContent');
        this.contextList = document.getElementById('contextList');
        this.responseMeta = document.getElementById('responseMeta');
        this.loadingText = document.getElementById('loadingText');
    }

    bindEvents() {
        this.askButton.addEventListener('click', () => this.askQuestion());
        this.questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                this.askQuestion();
            }
        });
        
        // Auto-resize textarea
        this.questionInput.addEventListener('input', () => {
            this.questionInput.style.height = 'auto';
            this.questionInput.style.height = this.questionInput.scrollHeight + 'px';
        });
    }

    async checkSystemStatus() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            if (data.status === 'healthy') {
                this.updateStatusIndicator('healthy', 'System Ready');
            } else {
                this.updateStatusIndicator('error', 'System Error');
            }
        } catch (error) {
            this.updateStatusIndicator('error', 'Connection Failed');
            console.error('Status check failed:', error);
        }
    }

    updateStatusIndicator(status, message) {
        this.statusIndicator.className = `status-indicator ${status}`;
        this.statusIndicator.innerHTML = `
            <i class="fas fa-circle"></i>
            <span>${message}</span>
        `;
    }

    async loadExamples() {
        try {
            const response = await fetch('/api/examples');
            const examples = await response.json();
            this.renderExamples(examples);
        } catch (error) {
            console.error('Failed to load examples:', error);
        }
    }

    renderExamples(examples) {
        this.examplesGrid.innerHTML = examples.map(category => `
            <div class="example-category">
                <h4><i class="fas fa-tag"></i> ${category.category}</h4>
                ${category.questions.map(question => `
                    <div class="example-question" onclick="app.fillQuestion('${question.replace(/'/g, "\\'")}')">
                        ${question}
                    </div>
                `).join('')}
            </div>
        `).join('');
    }

    fillQuestion(question) {
        this.questionInput.value = question;
        this.questionInput.focus();
        
        // Scroll to question input
        this.questionInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    async askQuestion() {
        const question = this.questionInput.value.trim();
        if (!question) {
            alert('Please enter a question');
            return;
        }

        // Show loading state
        this.showLoading('Searching for relevant context...');
        this.hideSection(this.responseSection);
        this.hideSection(this.examplesSection);
        
        // Disable button
        this.askButton.disabled = true;
        this.askButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

        try {
            const response = await fetch('/api/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: question,
                    context_limit: parseInt(this.contextLimit.value)
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.message || data.error);
            }

            this.displayResponse(data);
            
        } catch (error) {
            this.displayError(error.message);
            console.error('Question processing failed:', error);
        } finally {
            // Re-enable button
            this.askButton.disabled = false;
            this.askButton.innerHTML = '<i class="fas fa-search"></i> Ask Question';
            this.hideLoading();
        }
    }

    displayResponse(data) {
        // Update metadata
        this.responseMeta.innerHTML = `
            <div>
                <i class="fas fa-clock"></i> ${data.total_time}s total 
                (${data.search_time}s search + ${data.generation_time}s generation)
            </div>
            <div>
                <i class="fas fa-brain"></i> ${data.model}
            </div>
        `;

        // Display answer
        this.answerContent.innerHTML = this.formatAnswer(data.answer);

        // Display context sources
        this.contextList.innerHTML = data.contexts.map((context, index) => `
            <div class="context-item">
                <div class="context-header">
                    <div class="context-episode">
                        Episode ${context.episode_number}: ${context.episode_title}
                    </div>
                    <div class="context-score">
                        ${(context.score * 100).toFixed(1)}% match
                    </div>
                </div>
                <div class="context-timestamp">
                    <i class="fas fa-clock"></i> ${context.timestamp}
                </div>
                <div class="context-text">
                    ${this.highlightRelevantText(context.text, data.question)}
                </div>
            </div>
        `).join('');

        this.showSection(this.responseSection);
        
        // Scroll to response
        this.responseSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    formatAnswer(answer) {
        // Basic formatting for better readability
        return answer
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>')
            // Make episode references bold
            .replace(/Episode \d+/g, '<strong>$&</strong>')
            // Make important names bold (basic heuristic)
            .replace(/\b(Caesar|Augustus|Cicero|Pompey|Crassus|Hannibal|Constantine)\b/g, '<strong>$1</strong>');
    }

    highlightRelevantText(text, question) {
        // Simple highlighting of question terms in context
        const questionWords = question.toLowerCase().split(/\s+/).filter(word => word.length > 3);
        let highlightedText = text;
        
        questionWords.forEach(word => {
            const regex = new RegExp(`\\b${word}\\b`, 'gi');
            highlightedText = highlightedText.replace(regex, `<mark>$&</mark>`);
        });
        
        return highlightedText;
    }

    displayError(message) {
        this.answerContent.innerHTML = `
            <div style="color: var(--error-color); padding: 20px; text-align: center;">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Error</h3>
                <p>${message}</p>
                <p style="margin-top: 15px; font-size: 0.9rem; opacity: 0.8;">
                    Please try again or check if the system is running properly.
                </p>
            </div>
        `;
        
        this.contextList.innerHTML = '';
        this.responseMeta.innerHTML = '';
        this.showSection(this.responseSection);
    }

    showLoading(message) {
        this.loadingText.textContent = message;
        this.showSection(this.loadingSection);
    }

    hideLoading() {
        this.hideSection(this.loadingSection);
    }

    showSection(section) {
        section.style.display = 'block';
        section.classList.add('fade-in');
    }

    hideSection(section) {
        section.style.display = 'none';
        section.classList.remove('fade-in');
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new HistoryOfRomeApp();
});

// Utility functions
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Could add a toast notification here
        console.log('Copied to clipboard');
    });
}

// Add some keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + / to focus on question input
    if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        document.getElementById('questionInput').focus();
    }
});
