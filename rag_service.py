#!/usr/bin/env python3
"""
RAG Service for History of Rome

Combines Qdrant vector search with Ollama LLM to answer questions
about Roman history using podcast transcript data.
"""

import os
import logging
from typing import List, Dict, Optional
import time

import ollama
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HistoryOfRomeRAG:
    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        ollama_host: str = "localhost", 
        ollama_port: int = 11434,
        collection_name: str = "history_of_rome",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        ollama_model: str = "llama3.1:8b",
        max_context_length: int = 4000
    ):
        """Initialize the RAG service"""
        self.collection_name = collection_name
        self.ollama_model = ollama_model
        self.max_context_length = max_context_length
        
        # Initialize Qdrant client
        logger.info(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port}")
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        
        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.encoder = SentenceTransformer(embedding_model)
        
        # Initialize Ollama client
        logger.info(f"Connecting to Ollama at {ollama_host}:{ollama_port}")
        self.ollama_client = ollama.Client(host=f"http://{ollama_host}:{ollama_port}")
        
        # Verify connections
        self._verify_connections()
    
    def _verify_connections(self):
        """Verify that all services are accessible"""
        try:
            # Test Qdrant
            collections = self.qdrant_client.get_collections()
            logger.info(f"✓ Qdrant connected - {len(collections.collections)} collections")
            
            # Test Ollama
            models = self.ollama_client.list()
            model_names = [model['name'] for model in models['models']]
            logger.info(f"✓ Ollama connected - Available models: {model_names}")
            
            if self.ollama_model not in model_names:
                logger.warning(f"Model {self.ollama_model} not found. Available: {model_names}")
                # Try to pull the model
                logger.info(f"Attempting to pull {self.ollama_model}...")
                self.ollama_client.pull(self.ollama_model)
                logger.info(f"✓ Successfully pulled {self.ollama_model}")
            
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            raise
    
    def search_relevant_context(self, question: str, limit: int = 5) -> List[Dict]:
        """Search for relevant context from the podcast transcripts"""
        try:
            # Generate query embedding
            query_vector = self.encoder.encode([question])[0].tolist()
            
            # Search Qdrant
            search_results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                with_payload=True
            )
            
            # Format results
            contexts = []
            for hit in search_results:
                contexts.append({
                    'text': hit.payload['text'],
                    'episode_title': hit.payload['episode_title'],
                    'episode_number': hit.payload['episode_number'],
                    'timestamp': f"{hit.payload['timestamp_start']} --> {hit.payload['timestamp_end']}",
                    'score': hit.score
                })
            
            return contexts
            
        except Exception as e:
            logger.error(f"Context search failed: {e}")
            return []
    
    def build_prompt(self, question: str, contexts: List[Dict]) -> str:
        """Build a prompt for the LLM with context and question"""
        
        # Build context section
        context_text = ""
        total_length = 0
        
        for i, ctx in enumerate(contexts, 1):
            episode_info = f"Episode {ctx['episode_number']}: {ctx['episode_title']} [{ctx['timestamp']}]"
            context_entry = f"\n--- Context {i} ({episode_info}) ---\n{ctx['text']}\n"
            
            # Check if adding this context would exceed our limit
            if total_length + len(context_entry) > self.max_context_length:
                break
                
            context_text += context_entry
            total_length += len(context_entry)
        
        # Build the full prompt
        prompt = f"""You are an expert on Roman history, specifically knowledgeable about Mike Duncan's "The History of Rome" podcast series. You have access to timestamped transcripts from the podcast episodes.

Based on the following context from the podcast transcripts, please answer the user's question about Roman history. Be accurate, informative, and reference specific episodes when relevant.

CONTEXT FROM PODCAST TRANSCRIPTS:
{context_text}

QUESTION: {question}

Please provide a comprehensive answer based on the context above. If the context doesn't contain enough information to fully answer the question, say so and provide what information you can. Always mention which episode(s) the information comes from when possible.

ANSWER:"""

        return prompt
    
    def generate_answer(self, prompt: str) -> Dict:
        """Generate an answer using Ollama"""
        try:
            start_time = time.time()
            
            response = self.ollama_client.chat(
                model=self.ollama_model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                options={
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'max_tokens': 1000
                }
            )
            
            generation_time = time.time() - start_time
            
            return {
                'answer': response['message']['content'],
                'model': self.ollama_model,
                'generation_time': round(generation_time, 2)
            }
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {
                'answer': f"I apologize, but I encountered an error while generating the answer: {str(e)}",
                'model': self.ollama_model,
                'generation_time': 0,
                'error': True
            }
    
    def ask_question(self, question: str, context_limit: int = 5) -> Dict:
        """Complete RAG pipeline: search context + generate answer"""
        logger.info(f"Processing question: {question}")
        
        # Step 1: Search for relevant context
        start_time = time.time()
        contexts = self.search_relevant_context(question, limit=context_limit)
        search_time = time.time() - start_time
        
        if not contexts:
            return {
                'question': question,
                'answer': "I couldn't find relevant information in the podcast transcripts to answer your question.",
                'contexts': [],
                'search_time': round(search_time, 2),
                'generation_time': 0,
                'total_time': round(search_time, 2)
            }
        
        # Step 2: Build prompt with context
        prompt = self.build_prompt(question, contexts)
        
        # Step 3: Generate answer
        result = self.generate_answer(prompt)
        
        total_time = search_time + result['generation_time']
        
        return {
            'question': question,
            'answer': result['answer'],
            'contexts': contexts,
            'search_time': round(search_time, 2),
            'generation_time': result['generation_time'],
            'total_time': round(total_time, 2),
            'model': result['model'],
            'error': result.get('error', False)
        }
    
    def get_system_status(self) -> Dict:
        """Get status of all system components"""
        status = {
            'qdrant': {'status': 'unknown', 'details': ''},
            'ollama': {'status': 'unknown', 'details': ''},
            'collection': {'status': 'unknown', 'details': ''}
        }
        
        # Check Qdrant
        try:
            collections = self.qdrant_client.get_collections()
            status['qdrant'] = {
                'status': 'healthy',
                'details': f"{len(collections.collections)} collections available"
            }
        except Exception as e:
            status['qdrant'] = {'status': 'error', 'details': str(e)}
        
        # Check Ollama
        try:
            models = self.ollama_client.list()
            model_names = [model['name'] for model in models['models']]
            status['ollama'] = {
                'status': 'healthy',
                'details': f"Models: {', '.join(model_names)}"
            }
        except Exception as e:
            status['ollama'] = {'status': 'error', 'details': str(e)}
        
        # Check Collection
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            status['collection'] = {
                'status': 'healthy',
                'details': f"{collection_info.points_count} points loaded"
            }
        except Exception as e:
            status['collection'] = {'status': 'error', 'details': str(e)}
        
        return status

def create_rag_service() -> HistoryOfRomeRAG:
    """Factory function to create RAG service with environment configuration"""
    return HistoryOfRomeRAG(
        qdrant_host=os.getenv('QDRANT_HOST', 'localhost'),
        qdrant_port=int(os.getenv('QDRANT_PORT', '6333')),
        ollama_host=os.getenv('OLLAMA_HOST', 'localhost'),
        ollama_port=int(os.getenv('OLLAMA_PORT', '11434')),
        collection_name=os.getenv('COLLECTION_NAME', 'history_of_rome'),
        embedding_model=os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'),
        ollama_model=os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
    )
