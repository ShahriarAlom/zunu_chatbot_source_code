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

async def clean_and_reingest():
    docs_dir = "/app/knowledge_Base_doc"
    docx_files = glob.glob(os.path.join(docs_dir, "*.docx"))
    
    if not docx_files:
        print(f"No docx files found in {docs_dir}")
        return

    print(f"Found {len(docx_files)} documents in local folder.")
    
    async with async_session() as db:
        # Step 1: Clean duplicates in kb_documents
        print("Cleaning duplicate documents in the database...")
        # Get all documents in DB
        res = await db.execute(text("SELECT document_id, file_name, status FROM kb_documents"))
        db_docs = res.all()
        
        # Group by file_name
        grouped = {}
        for doc_id, file_name, status in db_docs:
            if file_name not in grouped:
                grouped[file_name] = []
            grouped[file_name].append({"id": doc_id, "status": status})
            
        for file_name, entries in grouped.items():
            if len(entries) > 1:
                # Find the best one (prefer active status, then highest ID)
                best_entry = None
                for entry in entries:
                    if entry["status"] == "active":
                        best_entry = entry
                        break
                if not best_entry:
                    best_entry = sorted(entries, key=lambda x: x["id"])[-1]
                
                # Delete all other entries
                other_ids = [entry["id"] for entry in entries if entry["id"] != best_entry["id"]]
                print(f"File '{file_name}': Keeping ID {best_entry['id']}, deleting duplicate IDs: {other_ids}")
                
                # Delete associated chunk embeddings first (just in case cascade isn't fully active)
                await db.execute(
                    text("DELETE FROM kb_chunk_embeddings WHERE document_id IN :ids"),
                    {"ids": tuple(other_ids)}
                )
                # Delete documents
                await db.execute(
                    text("DELETE FROM kb_documents WHERE document_id IN :ids"),
                    {"ids": tuple(other_ids)}
                )
                await db.commit()

        # Step 2: Ingest missing or incomplete documents
        print("\nChecking for missing or incomplete documents...")
        for idx, file_path in enumerate(docx_files, start=1):
            filename = os.path.basename(file_path)
            title = filename.replace("Knowledge Base Document ", "").replace(".docx", "")
            
            # Check if this document exists in DB and is active
            res = await db.execute(
                text("SELECT document_id, status FROM kb_documents WHERE file_name = :filename"),
                {"filename": filename}
            )
            doc_row = res.first()
            
            doc_id = None
            should_process = False
            
            if doc_row:
                doc_id = doc_row[0]
                status = doc_row[1]
                
                # Check chunk count for this document
                res_chunks = await db.execute(
                    text("SELECT COUNT(*) FROM kb_chunk_embeddings WHERE document_id = :doc_id"),
                    {"doc_id": doc_id}
                )
                chunk_count = res_chunks.scalar()
                
                if status == "active" and chunk_count > 0:
                    print(f"[{idx}/{len(docx_files)}] Skipping '{title}': Already active with {chunk_count} chunks.")
                    continue
                else:
                    print(f"[{idx}/{len(docx_files)}] Re-processing '{title}': Status='{status}', Chunks={chunk_count}")
                    should_process = True
            else:
                # Insert new document
                print(f"[{idx}/{len(docx_files)}] New document found: '{title}'. Inserting...")
                insert_res = await db.execute(
                    text("""
                        INSERT INTO kb_documents (category_id, title, file_name, cloudflare_r2_key, status)
                        VALUES (5, :title, :filename, 'local_import', 'processing')
                    """),
                    {"title": title[:255], "filename": filename[:255]}
                )
                doc_id = insert_res.lastrowid
                await db.commit()
                should_process = True
                
            if should_process:
                # Read DOCX content
                try:
                    doc = Document(file_path)
                    full_text = []
                    for para in doc.paragraphs:
                        full_text.append(para.text)
                    source_text = "\n".join(full_text).strip()
                    
                    if not source_text:
                        print(f"  -> Skipping '{title}': Empty document.")
                        await db.execute(
                            text("UPDATE kb_documents SET status = 'error' WHERE document_id = :doc_id"),
                            {"doc_id": doc_id}
                        )
                        await db.commit()
                        continue
                        
                    # Call process_document_background
                    await process_document_background(doc_id, source_text, db)
                    
                    # Update status to active
                    await db.execute(
                        text("UPDATE kb_documents SET status = 'active' WHERE document_id = :doc_id"),
                        {"doc_id": doc_id}
                    )
                    await db.commit()
                    
                    # Sleep to prevent hitting Gemini rate limits
                    print(f"  -> Successfully embedded '{title}'. Sleeping 6s...")
                    await asyncio.sleep(6)
                except Exception as e:
                    print(f"  -> Failed to process '{title}': {e}")
                    await db.execute(
                        text("UPDATE kb_documents SET status = 'error' WHERE document_id = :doc_id"),
                        {"doc_id": doc_id}
                    )
                    await db.commit()

        print("\nClean and re-ingest run completed successfully!")

if __name__ == "__main__":
    asyncio.run(clean_and_reingest())
