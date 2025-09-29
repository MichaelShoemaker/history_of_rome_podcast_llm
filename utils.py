#!/usr/bin/env python3
"""
Utility functions for the History of Rome podcast processing
"""

import re
from typing import List, Dict, Optional
from qdrant_client import QdrantClient

def search_episodes(
    client: QdrantClient,
    collection_name: str,
    query: str,
    limit: int = 5,
    episode_filter: Optional[int] = None
) -> List[Dict]:
    """
    Search for relevant segments in the History of Rome transcripts
    
    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
        query: Search query
        limit: Number of results to return
        episode_filter: Optional episode number to filter by
    
    Returns:
        List of search results with metadata
    """
    from sentence_transformers import SentenceTransformer
    
    # Initialize encoder (you might want to cache this)
    encoder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
    # Generate query embedding
    query_vector = encoder.encode([query])[0].tolist()
    
    # Prepare filter if episode specified
    query_filter = None
    if episode_filter:
        query_filter = {
            "must": [
                {
                    "key": "episode_number",
                    "match": {"value": episode_filter}
                }
            ]
        }
    
    # Search
    search_results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True
    )
    
    # Format results
    results = []
    for hit in search_results:
        results.append({
            'score': hit.score,
            'text': hit.payload['text'],
            'episode_title': hit.payload['episode_title'],
            'episode_number': hit.payload['episode_number'],
            'timestamp': f"{hit.payload['timestamp_start']} --> {hit.payload['timestamp_end']}",
            'duration': hit.payload['duration']
        })
    
    return results

def get_episode_summary(
    client: QdrantClient,
    collection_name: str,
    episode_number: int,
    max_segments: int = 10
) -> Dict:
    """
    Get a summary of an episode by retrieving key segments
    
    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
        episode_number: Episode number to summarize
        max_segments: Maximum number of segments to retrieve
    
    Returns:
        Dictionary with episode information and key segments
    """
    # Search for segments from the specific episode
    results = client.scroll(
        collection_name=collection_name,
        scroll_filter={
            "must": [
                {
                    "key": "episode_number",
                    "match": {"value": episode_number}
                }
            ]
        },
        limit=max_segments,
        with_payload=True
    )
    
    if not results[0]:  # No segments found
        return None
    
    segments = []
    episode_title = ""
    total_duration = 0
    
    for point in results[0]:
        if not episode_title:
            episode_title = point.payload['episode_title']
        
        segments.append({
            'text': point.payload['text'],
            'timestamp': f"{point.payload['timestamp_start']} --> {point.payload['timestamp_end']}",
            'duration': point.payload['duration']
        })
        total_duration += point.payload['duration']
    
    return {
        'episode_number': episode_number,
        'episode_title': episode_title,
        'total_segments': len(segments),
        'segments': segments,
        'estimated_duration': total_duration
    }

def find_historical_figures(
    client: QdrantClient,
    collection_name: str,
    figure_name: str,
    limit: int = 10
) -> List[Dict]:
    """
    Find mentions of historical figures across episodes
    
    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
        figure_name: Name of the historical figure
        limit: Number of results to return
    
    Returns:
        List of segments mentioning the figure
    """
    return search_episodes(client, collection_name, figure_name, limit)

def get_collection_stats(client: QdrantClient, collection_name: str) -> Dict:
    """
    Get statistics about the loaded collection
    
    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
    
    Returns:
        Dictionary with collection statistics
    """
    try:
        collection_info = client.get_collection(collection_name)
        
        # Get a sample of points to analyze
        sample_results = client.scroll(
            collection_name=collection_name,
            limit=1000,
            with_payload=True
        )
        
        episodes = set()
        total_duration = 0
        languages = set()
        
        for point in sample_results[0]:
            episodes.add(point.payload.get('episode_number', 0))
            total_duration += point.payload.get('duration', 0)
            languages.add(point.payload.get('language', 'unknown'))
        
        return {
            'total_points': collection_info.points_count,
            'total_vectors': collection_info.vectors_count,
            'unique_episodes': len(episodes),
            'episode_range': f"{min(episodes)} - {max(episodes)}" if episodes else "Unknown",
            'estimated_total_duration_seconds': total_duration,
            'estimated_total_duration_hours': round(total_duration / 3600, 1),
            'languages': list(languages),
            'vector_size': collection_info.config.params.vectors.size if hasattr(collection_info.config.params, 'vectors') else 'Unknown'
        }
    
    except Exception as e:
        return {'error': str(e)}

def format_search_results(results: List[Dict]) -> str:
    """
    Format search results for display
    
    Args:
        results: List of search results from search_episodes
    
    Returns:
        Formatted string for display
    """
    if not results:
        return "No results found."
    
    output = []
    for i, result in enumerate(results, 1):
        output.append(f"\n--- Result {i} (Score: {result['score']:.3f}) ---")
        output.append(f"Episode: {result['episode_title']}")
        output.append(f"Time: {result['timestamp']} ({result['duration']}s)")
        output.append(f"Text: {result['text']}")
    
    return "\n".join(output)
