#!/usr/bin/env python3
"""
Example queries for the History of Rome Qdrant database

This script demonstrates how to search and interact with the loaded
History of Rome transcripts in Qdrant.
"""

from qdrant_client import QdrantClient
from utils import search_episodes, find_historical_figures, get_episode_summary, format_search_results

def main():
    """Run example queries against the History of Rome database"""
    
    # Connect to Qdrant
    client = QdrantClient("localhost", port=6333)
    collection_name = "history_of_rome"
    
    print("🏛️ History of Rome - Example Queries")
    print("=" * 50)
    
    # Example 1: General historical question
    print("\n1. 📜 General Question: 'What caused the fall of the Roman Republic?'")
    results = search_episodes(client, collection_name, "What caused the fall of the Roman Republic?", limit=3)
    print(format_search_results(results))
    
    # Example 2: Specific battle
    print("\n2. ⚔️ Military History: 'Battle of Cannae tactics'")
    results = search_episodes(client, collection_name, "Battle of Cannae tactics", limit=3)
    print(format_search_results(results))
    
    # Example 3: Historical figure
    print("\n3. 👑 Historical Figure: 'Julius Caesar assassination'")
    results = find_historical_figures(client, collection_name, "Julius Caesar assassination", limit=3)
    print(format_search_results(results))
    
    # Example 4: Episode-specific search
    print("\n4. 🎯 Episode-Specific: 'Hannibal' in Episode 23")
    results = search_episodes(client, collection_name, "Hannibal crossing Alps", limit=2, episode_filter=23)
    print(format_search_results(results))
    
    # Example 5: Get episode summary
    print("\n5. 📋 Episode Summary: Episode 46 - 'Sic Semper Tyrannis' (Caesar's assassination)")
    summary = get_episode_summary(client, collection_name, 46, max_segments=3)
    if summary:
        print(f"\nEpisode: {summary['episode_title']}")
        print(f"Segments found: {summary['total_segments']}")
        print(f"Estimated duration: {summary['estimated_duration']} seconds")
        print("\nKey segments:")
        for i, segment in enumerate(summary['segments'][:3], 1):
            print(f"\n  Segment {i} [{segment['timestamp']}]:")
            print(f"  {segment['text'][:200]}...")
    
    # Example 6: Timeline search
    print("\n6. 📅 Timeline Search: 'Punic Wars'")
    results = search_episodes(client, collection_name, "Punic Wars Hannibal Carthage", limit=4)
    print(format_search_results(results))
    
    # Example 7: Political concepts
    print("\n7. 🏛️ Political Concepts: 'Roman Senate corruption'")
    results = search_episodes(client, collection_name, "Roman Senate corruption politics", limit=3)
    print(format_search_results(results))
    
    print("\n" + "=" * 50)
    print("✨ Try your own queries using the functions in utils.py!")
    print("Example:")
    print("  results = search_episodes(client, 'history_of_rome', 'your question here')")
    print("  print(format_search_results(results))")

if __name__ == "__main__":
    main()
