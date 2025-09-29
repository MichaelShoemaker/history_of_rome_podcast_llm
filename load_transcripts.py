#!/usr/bin/env python3
"""
History of Rome Transcript Loader for Qdrant

This script loads timestamped transcripts from The History of Rome podcast
into a Qdrant vector database for semantic search and LLM applications.
"""

import os
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HistoryOfRomeLoader:
    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "history_of_rome",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ):
        """Initialize the transcript loader"""
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize Qdrant client
        logger.info(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port}")
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        
        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.encoder = SentenceTransformer(embedding_model)
        self.vector_size = self.encoder.get_sentence_embedding_dimension()
        
        # Initialize collection
        self._setup_collection()
    
    def _setup_collection(self):
        """Create or recreate the Qdrant collection"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name in collection_names:
                logger.info(f"Collection '{self.collection_name}' already exists. Recreating...")
                self.client.delete_collection(self.collection_name)
            
            # Create new collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created collection '{self.collection_name}' with vector size {self.vector_size}")
            
        except Exception as e:
            logger.error(f"Failed to setup collection: {e}")
            raise
    
    def parse_transcript(self, file_path: Path) -> Dict:
        """Parse a single transcript file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.strip().split('\n')
            
            # Extract metadata from header
            metadata = {
                'episode_title': '',
                'language': 'en',
                'duration': 0.0,
                'model': 'unknown',
                'device': 'unknown',
                'file_path': str(file_path)
            }
            
            # Parse header
            transcript_lines = []
            for i, line in enumerate(lines):
                if line.startswith('#'):
                    if i == 0:  # Episode title
                        metadata['episode_title'] = line[1:].strip()
                    elif 'Detected language:' in line:
                        metadata['language'] = line.split(':')[1].strip()
                    elif 'Duration:' in line:
                        duration_match = re.search(r'(\d+\.?\d*)', line)
                        if duration_match:
                            metadata['duration'] = float(duration_match.group(1))
                    elif 'Model:' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            metadata['model'] = parts[0].split(':')[1].strip()
                            metadata['device'] = parts[1].split(':')[1].strip()
                elif line.strip() and not line.startswith('#'):
                    transcript_lines.append(line)
            
            # Parse timestamped segments
            segments = []
            for line in transcript_lines:
                # Match timestamp pattern [MM:SS --> MM:SS] text
                timestamp_match = re.match(r'\[(\d{2}):(\d{2}) --> (\d{2}):(\d{2})\]\s*(.*)', line)
                if timestamp_match:
                    start_min, start_sec, end_min, end_sec, text = timestamp_match.groups()
                    start_time = int(start_min) * 60 + int(start_sec)
                    end_time = int(end_min) * 60 + int(end_sec)
                    
                    segments.append({
                        'start_time': start_time,
                        'end_time': end_time,
                        'text': text.strip(),
                        'timestamp': f"[{start_min}:{start_sec} --> {end_min}:{end_sec}]"
                    })
            
            return {
                'metadata': metadata,
                'segments': segments
            }
            
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None
    
    def chunk_text(self, segments: List[Dict], episode_metadata: Dict) -> List[Dict]:
        """Create overlapping chunks from segments for better context"""
        chunks = []
        current_chunk = ""
        current_segments = []
        current_start_time = None
        
        for segment in segments:
            # If adding this segment would exceed chunk size, create a chunk
            potential_chunk = current_chunk + " " + segment['text'] if current_chunk else segment['text']
            
            if len(potential_chunk) > self.chunk_size and current_chunk:
                # Create chunk from current segments
                chunks.append({
                    'text': current_chunk.strip(),
                    'start_time': current_start_time,
                    'end_time': current_segments[-1]['end_time'],
                    'segments': current_segments.copy(),
                    'episode_title': episode_metadata['episode_title'],
                    'episode_metadata': episode_metadata
                })
                
                # Start new chunk with overlap
                overlap_text = ""
                overlap_segments = []
                overlap_chars = 0
                
                # Add segments from the end for overlap
                for seg in reversed(current_segments):
                    if overlap_chars + len(seg['text']) <= self.chunk_overlap:
                        overlap_text = seg['text'] + " " + overlap_text if overlap_text else seg['text']
                        overlap_segments.insert(0, seg)
                        overlap_chars += len(seg['text'])
                    else:
                        break
                
                current_chunk = overlap_text + " " + segment['text'] if overlap_text else segment['text']
                current_segments = overlap_segments + [segment]
                current_start_time = overlap_segments[0]['start_time'] if overlap_segments else segment['start_time']
            else:
                # Add segment to current chunk
                current_chunk = potential_chunk
                current_segments.append(segment)
                if current_start_time is None:
                    current_start_time = segment['start_time']
        
        # Add final chunk if it exists
        if current_chunk:
            chunks.append({
                'text': current_chunk.strip(),
                'start_time': current_start_time,
                'end_time': current_segments[-1]['end_time'],
                'segments': current_segments,
                'episode_title': episode_metadata['episode_title'],
                'episode_metadata': episode_metadata
            })
        
        return chunks
    
    def load_transcripts(self, transcript_dirs: List[str]):
        """Load all transcripts from specified directories"""
        all_files = []
        
        # Collect all transcript files
        for dir_path in transcript_dirs:
            if os.path.exists(dir_path):
                dir_files = list(Path(dir_path).glob("*.txt"))
                all_files.extend(dir_files)
                logger.info(f"Found {len(dir_files)} files in {dir_path}")
            else:
                logger.warning(f"Directory not found: {dir_path}")
        
        if not all_files:
            logger.error("No transcript files found!")
            return
        
        logger.info(f"Processing {len(all_files)} transcript files...")
        
        # Process all files
        all_chunks = []
        failed_files = []
        
        for file_path in tqdm(all_files, desc="Parsing transcripts"):
            parsed = self.parse_transcript(file_path)
            if parsed:
                chunks = self.chunk_text(parsed['segments'], parsed['metadata'])
                all_chunks.extend(chunks)
                logger.debug(f"Created {len(chunks)} chunks from {file_path.name}")
            else:
                failed_files.append(file_path)
        
        if failed_files:
            logger.warning(f"Failed to parse {len(failed_files)} files: {[f.name for f in failed_files]}")
        
        logger.info(f"Created {len(all_chunks)} total chunks from {len(all_files) - len(failed_files)} files")
        
        # Generate embeddings and upload
        self._upload_chunks(all_chunks)
    
    def _upload_chunks(self, chunks: List[Dict]):
        """Generate embeddings and upload chunks to Qdrant"""
        logger.info("Generating embeddings...")
        
        # Extract texts for embedding
        texts = [chunk['text'] for chunk in chunks]
        
        # Generate embeddings in batches
        batch_size = 32
        embeddings = []
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = self.encoder.encode(batch_texts, show_progress_bar=False)
            embeddings.extend(batch_embeddings.tolist())
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        # Prepare points for upload
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Extract episode number from title for better organization
            episode_match = re.search(r'(\d+)', chunk['episode_title'])
            episode_number = int(episode_match.group(1)) if episode_match else 0
            
            point = PointStruct(
                id=i,
                vector=embedding,
                payload={
                    'text': chunk['text'],
                    'episode_title': chunk['episode_title'],
                    'episode_number': episode_number,
                    'start_time': chunk['start_time'],
                    'end_time': chunk['end_time'],
                    'duration': chunk['end_time'] - chunk['start_time'],
                    'language': chunk['episode_metadata']['language'],
                    'model': chunk['episode_metadata']['model'],
                    'device': chunk['episode_metadata']['device'],
                    'file_path': chunk['episode_metadata']['file_path'],
                    'segment_count': len(chunk['segments']),
                    'timestamp_start': f"{chunk['start_time'] // 60:02d}:{chunk['start_time'] % 60:02d}",
                    'timestamp_end': f"{chunk['end_time'] // 60:02d}:{chunk['end_time'] % 60:02d}"
                }
            )
            points.append(point)
        
        # Upload to Qdrant in batches
        logger.info("Uploading to Qdrant...")
        batch_size = 100
        
        for i in tqdm(range(0, len(points), batch_size), desc="Uploading to Qdrant"):
            batch_points = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch_points
            )
        
        logger.info(f"Successfully uploaded {len(points)} points to collection '{self.collection_name}'")
        
        # Print collection stats
        collection_info = self.client.get_collection(self.collection_name)
        logger.info(f"Collection stats: {collection_info.points_count} points, {collection_info.vectors_count} vectors")

def main():
    """Main function to load transcripts"""
    # Get configuration from environment variables
    qdrant_host = os.getenv('QDRANT_HOST', 'localhost')
    qdrant_port = int(os.getenv('QDRANT_PORT', '6333'))
    collection_name = os.getenv('COLLECTION_NAME', 'history_of_rome')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    chunk_size = int(os.getenv('CHUNK_SIZE', '512'))
    chunk_overlap = int(os.getenv('CHUNK_OVERLAP', '50'))
    
    logger.info("Starting History of Rome transcript loading...")
    logger.info(f"Configuration: Host={qdrant_host}, Port={qdrant_port}, Collection={collection_name}")
    
    # Wait for Qdrant to be ready
    logger.info("Waiting for Qdrant to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            client = QdrantClient(host=qdrant_host, port=qdrant_port)
            client.get_collections()
            logger.info("Qdrant is ready!")
            break
        except Exception as e:
            if i == max_retries - 1:
                logger.error(f"Failed to connect to Qdrant after {max_retries} attempts: {e}")
                return
            logger.info(f"Waiting for Qdrant... (attempt {i + 1}/{max_retries})")
            time.sleep(2)
    
    # Initialize loader
    loader = HistoryOfRomeLoader(
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        collection_name=collection_name,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    # Load transcripts from all_transcripts directory
    transcript_dirs = [
        'all_transcripts'
    ]
    
    loader.load_transcripts(transcript_dirs)
    logger.info("Transcript loading completed!")

if __name__ == "__main__":
    main()
