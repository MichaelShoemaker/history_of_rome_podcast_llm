#!/usr/bin/env python3
"""
History of Rome RAG Flask App

A web interface for asking questions about Roman history using
podcast transcripts, vector search, and LLM generation.
"""

import os
import logging
import time
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import json

from rag_service import create_rag_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for API access

# Global RAG service instance
rag_service = None

def initialize_rag_service():
    """Initialize the RAG service with retry logic"""
    global rag_service
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing RAG service (attempt {attempt + 1}/{max_retries})...")
            rag_service = create_rag_service()
            logger.info("✓ RAG service initialized successfully!")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Max retries reached. RAG service initialization failed.")
                return False
    
    return False

@app.route('/')
def index():
    """Main page with question interface"""
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    if rag_service is None:
        return jsonify({'status': 'error', 'message': 'RAG service not initialized'}), 503
    
    try:
        status = rag_service.get_system_status()
        return jsonify({
            'status': 'healthy',
            'components': status,
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': time.time()
        }), 500

@app.route('/api/ask', methods=['POST'])
def ask_question():
    """API endpoint for asking questions"""
    if rag_service is None:
        return jsonify({
            'error': 'RAG service not available',
            'message': 'The service is still initializing. Please try again in a moment.'
        }), 503
    
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'error': 'Missing question in request body'}), 400
        
        question = data['question'].strip()
        if not question:
            return jsonify({'error': 'Question cannot be empty'}), 400
        
        # Optional parameters
        context_limit = data.get('context_limit', 5)
        context_limit = max(1, min(10, context_limit))  # Clamp between 1-10
        
        # Process the question
        result = rag_service.ask_question(question, context_limit=context_limit)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/api/ask/stream', methods=['POST'])
def ask_question_stream():
    """Streaming API endpoint for real-time responses"""
    if rag_service is None:
        return jsonify({'error': 'RAG service not available'}), 503
    
    def generate():
        try:
            data = request.get_json()
            question = data['question'].strip()
            context_limit = data.get('context_limit', 5)
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Searching for relevant context...'})}\n\n"
            
            # Search for context
            contexts = rag_service.search_relevant_context(question, limit=context_limit)
            
            yield f"data: {json.dumps({'type': 'contexts', 'data': contexts})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'Generating answer...'})}\n\n"
            
            # Generate answer
            prompt = rag_service.build_prompt(question, contexts)
            result = rag_service.generate_answer(prompt)
            
            yield f"data: {json.dumps({'type': 'answer', 'data': result})}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/plain')

@app.route('/api/status')
def system_status():
    """Get detailed system status"""
    if rag_service is None:
        return jsonify({
            'status': 'initializing',
            'message': 'RAG service is still starting up'
        })
    
    try:
        status = rag_service.get_system_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/examples')
def example_questions():
    """Get example questions for the interface"""
    examples = [
        {
            'category': 'Political History',
            'questions': [
                "What caused the fall of the Roman Republic?",
                "How did Augustus transform Rome from a republic to an empire?",
                "What role did the Senate play in Roman politics?"
            ]
        },
        {
            'category': 'Military History', 
            'questions': [
                "How did Roman military tactics evolve over time?",
                "What happened at the Battle of Cannae?",
                "How did Rome defeat Hannibal and Carthage?"
            ]
        },
        {
            'category': 'Key Figures',
            'questions': [
                "Tell me about Julius Caesar's rise to power",
                "What was Cicero's role in Roman politics?",
                "How did Constantine change the Roman Empire?"
            ]
        },
        {
            'category': 'Social & Cultural',
            'questions': [
                "How did Roman society change over time?",
                "What was daily life like for ordinary Romans?",
                "How did Christianity spread throughout the Roman Empire?"
            ]
        }
    ]
    
    return jsonify(examples)

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    logger.info("🏛️ Starting History of Rome RAG Flask App")
    
    # Initialize RAG service
    if not initialize_rag_service():
        logger.error("Failed to initialize RAG service. Exiting.")
        exit(1)
    
    # Start Flask app
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Flask app on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
