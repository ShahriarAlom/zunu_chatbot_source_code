import json
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from rag_pipeline import embeddings
from config_service import get_ai_config

async def retrieve_context(user_query: str, db: AsyncSession, top_k: int = 4, distance_threshold: float = 0.3) -> str:
    """
    Takes a user query, generates a vector embedding, and searches the MariaDB
    vector index for the most relevant semantic chunks. 
    Implements a 'Context Buffer' by fetching surrounding chunks.
    """
    try:
        # Fetch dynamic settings
        config = await get_ai_config()
        # Admin panel stores 'confidence_threshold'. Vector DB distance = 1.0 - confidence
        distance_threshold = 1.0 - float(config.get("confidence_threshold", 0.70))
        top_k = int(config.get("top_k_chunks", 5))

        # Step 1: Embed the user's query
        query_vector = await embeddings.aembed_query(user_query)
        vector_json = json.dumps(query_vector)

        # Step 2: Build Hybrid Vector Search Query
        # We use VEC_DISTANCE_COSINE. Lower distance = higher similarity.
        # Threshold 0.3 means similarity > 0.7
        sql = text("""
            SELECT 
                ce.chunk_id, 
                ce.document_id, 
                ce.chunk_index, 
                ce.chunk_text, 
                d.title AS document_title,
                VEC_DISTANCE_COSINE(ce.embedding, VEC_FromText(:query_vec)) AS distance
            FROM kb_chunk_embeddings ce
            JOIN kb_documents d ON ce.document_id = d.document_id
            WHERE ce.is_active = 1
            ORDER BY distance ASC
            LIMIT :top_k
        """)
        
        result = await db.execute(sql, {"query_vec": vector_json, "top_k": top_k})
        best_matches = result.mappings().all()
        
        if not best_matches or best_matches[0]['distance'] > distance_threshold:
            return "" # No highly relevant context found
            
        # Step 3: Context Buffer Strategy
        # We want to pull the surrounding chunks for our best matches.
        # Example: If chunk 5 matched, we want chunks 4, 5, and 6 to provide the LLM with complete context.
        
        context_chunks = []
        fetched_keys = set() # Avoid duplicates if two adjacent chunks both match
        
        for match in best_matches:
            doc_id = match['document_id']
            base_idx = match['chunk_index']
            
            # We want index - 1, index, index + 1
            target_indices = [base_idx - 1, base_idx, base_idx + 1]
            
            for idx in target_indices:
                if idx < 0:
                    continue
                    
                key = f"{doc_id}_{idx}"
                if key in fetched_keys:
                    continue
                    
                # If it's the exact chunk we just retrieved, use it directly
                if idx == base_idx:
                    context_chunks.append({
                        "doc_title": match['document_title'],
                        "text": match['chunk_text']
                    })
                    fetched_keys.add(key)
                else:
                    # Otherwise, hit the DB quickly for the surrounding chunk
                    surrounding_sql = text("""
                        SELECT ce.chunk_text, d.title AS document_title
                        FROM kb_chunk_embeddings ce
                        JOIN kb_documents d ON ce.document_id = d.document_id
                        WHERE ce.document_id = :doc_id AND ce.chunk_index = :idx AND ce.is_active = 1
                    """)
                    sur_result = await db.execute(surrounding_sql, {"doc_id": doc_id, "idx": idx})
                    sur_match = sur_result.mappings().first()
                    if sur_match:
                        context_chunks.append({
                            "doc_title": sur_match['document_title'],
                            "text": sur_match['chunk_text']
                        })
                    fetched_keys.add(key)

        # Step 4: Compile into a single string for the LLM prompt
        compiled_context = "\n\n".join([f"--- SOURCE: {c['doc_title']} ---\n{c['text']}" for c in context_chunks])
        
        return compiled_context
        
    except Exception as e:
        print(f"Error in RAG retrieval: {e}")
        return ""
