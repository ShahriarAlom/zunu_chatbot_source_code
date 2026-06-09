import asyncio
import os
import glob
from docx import Document
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from rag_pipeline import process_document_background

LARAVEL_DB_URL = os.getenv("MARIADB_URI", "mysql+aiomysql://root:password@mariadb_chatbot:3306/realdealride_ai")
engine = create_async_engine(LARAVEL_DB_URL)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def run_ingestion():
    docs_dir = "/app/knowledge_Base_doc"
    docx_files = glob.glob(os.path.join(docs_dir, "*.docx"))
    txt_files = glob.glob(os.path.join(docs_dir, "*.txt"))
    all_files = docx_files + txt_files
    
    if not all_files:
        print(f"No docx or txt files found in {docs_dir}")
        return

    print(f"Found {len(all_files)} documents to ingest ({len(docx_files)} docx, {len(txt_files)} txt).")
    
    async with async_session() as db:
        for idx, file_path in enumerate(all_files, start=1):
            filename = os.path.basename(file_path)
            title = filename.replace("Knowledge Base Document ", "")
            if filename.endswith(".docx"):
                title = title.replace(".docx", "")
            elif filename.endswith(".txt"):
                title = title.replace(".txt", "")
            print(f"[{idx}/{len(all_files)}] Processing: {title}")
            
            # Read content
            try:
                if file_path.endswith(".txt"):
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        source_text = f.read().strip()
                else:
                    doc = Document(file_path)
                    full_text = []
                    for para in doc.paragraphs:
                        full_text.append(para.text)
                    source_text = "\n".join(full_text).strip()
                
                if not source_text:
                    print(f"  -> Skipping {title}: No text found.")
                    continue
                
                # Check if this document exists in DB
                res = await db.execute(
                    text("SELECT document_id, status, source_text FROM kb_documents WHERE file_name = :filename"),
                    {"filename": filename}
                )
                doc_row = res.first()
                
                document_id = None
                should_process = False
                
                if doc_row:
                    document_id = doc_row[0]
                    status = doc_row[1]
                    stored_text = doc_row[2] or ""
                    
                    # Check chunk count
                    res_chunks = await db.execute(
                        text("SELECT COUNT(*) FROM kb_chunk_embeddings WHERE document_id = :doc_id"),
                        {"doc_id": document_id}
                    )
                    chunk_count = res_chunks.scalar()
                    
                    if status == "active" and chunk_count > 0 and stored_text.strip() == source_text:
                        print(f"  -> Skipping '{title}': Already active and matches disk content.")
                        continue
                    else:
                        reason = "Content changed" if stored_text.strip() != source_text else f"Status='{status}' or Chunks={chunk_count}"
                        print(f"  -> Re-processing '{title}': {reason}")
                        # Purge chunks
                        await db.execute(
                            text("DELETE FROM kb_chunk_embeddings WHERE document_id = :doc_id"),
                            {"doc_id": document_id}
                        )
                        # Update status and source_text
                        await db.execute(
                            text("UPDATE kb_documents SET status = 'processing', source_text = :source_text WHERE document_id = :doc_id"),
                            {"doc_id": document_id, "source_text": source_text}
                        )
                        await db.commit()
                        should_process = True
                else:
                    print(f"  -> New document found: '{title}'. Inserting...")
                    # Insert into kb_documents
                    insert_doc_sql = text("""
                        INSERT INTO kb_documents (category_id, title, file_name, cloudflare_r2_key, status, source_text)
                        VALUES (5, :title, :file_name, 'local_import', 'processing', :source_text)
                    """)
                    res = await db.execute(insert_doc_sql, {
                        "title": title[:255],
                        "file_name": filename[:255],
                        "source_text": source_text
                    })
                    document_id = res.lastrowid
                    await db.commit()
                    should_process = True
                
                if should_process:
                    # Process chunks and embeddings (uses Gemini API)
                    await process_document_background(document_id, source_text, db)
                    
                    # Update status to active
                    await db.execute(
                        text("UPDATE kb_documents SET status = 'active' WHERE document_id = :doc_id"),
                        {"doc_id": document_id}
                    )
                    await db.commit()
                    
                    # Sleep to prevent hitting Gemini API rate limits
                    print(f"  -> Finished {title}. Sleeping 4s to respect rate limits...")
                    await asyncio.sleep(4)
                
            except Exception as e:
                print(f"  -> Failed to process {filename}: {e}")

if __name__ == "__main__":
    asyncio.run(run_ingestion())
