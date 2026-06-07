import os
import json
import asyncio
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini Embeddings (768 dimensions for embedding-001)
# Make sure your database table kb_chunk_embeddings uses VECTOR(768) in production!
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Standard Fallback Splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", " ", ""]
)

async def process_document_background(document_id: int, source_text: str, db: AsyncSession = None):
    """
    Background task to process a document, chunk it, generate embeddings,
    and atomically insert it into MariaDB.
    """
    print(f"Starting background processing for document {document_id}")
    
    db_provided = db is not None
    if not db_provided:
        from database import AsyncSessionLocal
        db = AsyncSessionLocal()
    
    try:
        # Step 0: Save source_text in kb_documents table cell
        update_doc_query = text("UPDATE kb_documents SET source_text = :text, status = 'processing' WHERE document_id = :doc_id")
        await db.execute(update_doc_query, {"text": source_text, "doc_id": document_id})

        # Step 1: Chunking
        # In a full "Agentic" approach, we would use an LLM call here to find semantic breaks.
        # For efficiency, we use LangChain's Recursive splitter as the core engine.
        chunks = text_splitter.split_text(source_text)
        print(f"Document {document_id} split into {len(chunks)} chunks.")

        # Step 2: Delete existing chunks for atomic update
        delete_query = text("DELETE FROM kb_chunk_embeddings WHERE document_id = :doc_id")
        await db.execute(delete_query, {"doc_id": document_id})
        
        # Step 3: Embed and Insert
        # We process in small batches to avoid hitting API rate limits
        batch_size = 20
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            
            # Generate embeddings via Gemini API with retry on 429
            batch_embeddings = None
            for retry in range(5):
                try:
                    batch_embeddings = await embeddings.aembed_documents(batch_chunks)
                    break
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower() or "limit" in str(e).lower():
                        wait_time = (retry + 1) * 8
                        print(f"Rate limit hit. Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise e
            if not batch_embeddings:
                raise Exception("Failed to generate embeddings after multiple retries due to rate limits.")
            
            for j, (chunk_text, embedding_vector) in enumerate(zip(batch_chunks, batch_embeddings)):
                chunk_index = i + j
                
                # Format vector as a JSON array string for MariaDB's VEC_FromText
                vector_json = json.dumps(embedding_vector)
                
                # Raw SQL insert using VEC_FromText
                insert_query = text("""
                    INSERT INTO kb_chunk_embeddings 
                    (document_id, chunk_index, chunk_text, token_count, embedding_model, embedding)
                    VALUES 
                    (:doc_id, :idx, :text, :tokens, :model, VEC_FromText(:vec))
                """)
                
                # Rough token estimation (1 token ~= 4 chars)
                token_count = len(chunk_text) // 4
                
                await db.execute(insert_query, {
                    "doc_id": document_id,
                    "idx": chunk_index,
                    "text": chunk_text,
                    "tokens": token_count,
                    "model": "models/gemini-embedding-001",
                    "vec": vector_json
                })
        
        # Step 4: Update status to 'active' upon successful embedding
        update_status_query = text("UPDATE kb_documents SET status = 'active' WHERE document_id = :doc_id")
        await db.execute(update_status_query, {"doc_id": document_id})
        
        # Commit the entire transaction
        await db.commit()
        print(f"Successfully processed and embedded document {document_id}")
        
    except Exception as e:
        await db.rollback()
        print(f"Error processing document {document_id}: {e}")
        try:
            update_error_query = text("UPDATE kb_documents SET status = 'error' WHERE document_id = :doc_id")
            await db.execute(update_error_query, {"doc_id": document_id})
            await db.commit()
        except Exception as db_err:
            print(f"Failed to update document status to error: {db_err}")
        raise e
    finally:
        if not db_provided:
            await db.close()
