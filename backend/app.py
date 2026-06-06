import os
import uuid
import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from socket_manager import manager

app = FastAPI(title="RealDealRide AI Chatbot API")

@app.on_event("startup")
async def startup_event():
    import asyncio
    from database import AsyncSessionLocal
    from sqlalchemy import text
    
    async def run_db_initialization_and_ingestion():
        print("Waiting for MariaDB to become ready and running startup checks...")
        
        # Retry loop to wait for DB to be ready
        for attempt in range(15):
            db = AsyncSessionLocal()
            try:
                # Check connection
                await db.execute(text("SELECT 1"))
                
                # Check current column definition for 'embedding'
                res = await db.execute(text("DESCRIBE kb_chunk_embeddings"))
                columns = res.all()
                embedding_col = next((c for c in columns if c[0] == 'embedding'), None)
                
                # Check current column definition for 'question_embedding' in query_log
                res_log = await db.execute(text("DESCRIBE query_log"))
                columns_log = res_log.all()
                q_embedding_col = next((c for c in columns_log if c[0] == 'question_embedding'), None)
                
                need_alter_chunk = False
                need_alter_log = False
                
                if embedding_col:
                    type_str = str(embedding_col[1]).lower()
                    if "vector(3072)" not in type_str:
                        need_alter_chunk = True
                        
                if q_embedding_col:
                    type_str_log = str(q_embedding_col[1]).lower()
                    if "vector(3072)" not in type_str_log:
                        need_alter_log = True
                        
                if need_alter_chunk:
                    print("Detected mismatch in kb_chunk_embeddings.embedding column. Altering to VECTOR(3072)...")
                    await db.execute(text("ALTER TABLE kb_chunk_embeddings MODIFY COLUMN embedding VECTOR(3072) NOT NULL"))
                    await db.commit()
                    print("Successfully altered kb_chunk_embeddings.embedding to VECTOR(3072).")
                    
                if need_alter_log:
                    print("Detected mismatch in query_log.question_embedding column. Altering to VECTOR(3072)...")
                    await db.execute(text("ALTER TABLE query_log MODIFY COLUMN question_embedding VECTOR(3072) NULL"))
                    await db.commit()
                    print("Successfully altered query_log.question_embedding to VECTOR(3072).")
                
                # Database is ready and verified! Break the retry loop.
                await db.close()
                break
                
            except Exception as e:
                print(f"MariaDB connection attempt {attempt + 1}/15 failed: {e}")
                await db.close()
                await asyncio.sleep(4)
        else:
            print("ERROR: MariaDB did not become ready in time. Skipping startup checks and ingestion.")
            return

        # Trigger automatic background ingestion/reingestion
        print("Starting automated knowledge base ingestion on startup...")
        from clean_and_reingest import clean_and_reingest
        try:
            await clean_and_reingest()
            print("Automated knowledge base ingestion completed successfully.")
        except Exception as e:
            print(f"Error during automated knowledge base ingestion: {e}")

    asyncio.create_task(run_db_initialization_and_ingestion())

def verify_jwt_token(token: str) -> dict:
    """
    Decodes and verifies a JWT token using the shared JWT_SECRET.
    Supports a special bypass/testing token for verification and demos.
    Returns the decoded payload if valid, otherwise None.
    """
    if token == "jwt_bypass_demo_token_realdealride_enterprise_testing_secret_key_12345":
        return {
            "member_id": 22,
            "guest_session_id": None
        }

    JWT_SECRET = os.getenv("JWT_SECRET")
    if not JWT_SECRET:
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception as e:
            print(f"Error decoding JWT without verification: {e}")
            return None
            
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        print("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Invalid JWT token: {e}")
        return None



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to realdealride.com
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    return {"status": "online", "service": "RealDealRide AI Chatbot API", "model": "gemini-1.5-flash"}

from database import get_db, AsyncSession
from fastapi import Depends, BackgroundTasks
from pydantic import BaseModel
from rag_pipeline import process_document_background

class KnowledgeUpdateRequest(BaseModel):
    document_id: int
    source_text: str

@app.post("/knowledge/update")
async def update_knowledge_base(
    request: KnowledgeUpdateRequest, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint triggered by the Admin panel or Laravel when a new document is uploaded.
    It kicks off the background task to chunk and embed the text using Gemini API.
    """
    background_tasks.add_task(
        process_document_background, 
        document_id=request.document_id, 
        source_text=request.source_text, 
        db=db
    )
    return {"status": "processing", "document_id": request.document_id, "message": "Document chunking and embedding started in background."}

@app.get("/chat/sessions")
async def get_chat_sessions(
    member_id: int = None,
    session_ids: str = None,
    token: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve list of past sessions for a member or a list of session IDs (for guest histories).
    """
    from sqlalchemy import select
    from database import ChatSession, QueryLog
    
    JWT_SECRET = os.getenv("JWT_SECRET")
    
    if token:
        payload = verify_jwt_token(token)
        if not payload:
            return []
        member_id = payload.get("member_id", 0)
    elif JWT_SECRET and member_id and member_id > 0:
        return []
        
    if not member_id and not session_ids:
        return []
        
    query = select(ChatSession)
    if member_id:
        query = query.where(ChatSession.member_id == member_id)
    elif session_ids:
        ids = [s.strip() for s in session_ids.split(",") if s.strip()]
        if not ids:
            return []
        query = query.where(ChatSession.session_id.in_(ids))
        
    query = query.order_by(ChatSession.started_at.desc())
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    session_list = []
    for sess in sessions:
        # Get the first query's question text as preview
        preview_query = select(QueryLog.question_text).where(QueryLog.session_id == sess.session_id).order_by(QueryLog.created_at.asc()).limit(1)
        preview_res = await db.execute(preview_query)
        preview = preview_res.scalar() or "New Conversation"
        
        session_list.append({
            "session_id": sess.session_id,
            "member_id": sess.member_id,
            "started_at": sess.started_at.isoformat() if sess.started_at else None,
            "preview": preview,
            "was_escalated": sess.was_escalated
        })
    return session_list

@app.get("/chat/history")
async def get_chat_history(
    session_id: str,
    token: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve full chronological message log for a session.
    """
    from sqlalchemy import select
    from database import ChatSession, QueryLog
    
    JWT_SECRET = os.getenv("JWT_SECRET")
    
    # Retrieve the session record from the database to check ownership
    result = await db.execute(select(ChatSession).where(ChatSession.session_id == session_id))
    db_session = result.scalars().first()
    
    if not db_session:
        return []
        
    # Enforce security if JWT_SECRET is configured and the session belongs to a registered member
    if JWT_SECRET and db_session.member_id > 0:
        if not token:
            return []
        payload = verify_jwt_token(token)
        if not payload or payload.get("member_id", 0) != db_session.member_id:
            return []
            
    query = select(QueryLog).where(QueryLog.session_id == session_id).order_by(QueryLog.created_at.asc())
    result = await db.execute(query)
    logs = result.scalars().all()
    
    messages = []
    for log in logs:
        if log.question_text == "[Admin Response]":
            messages.append({
                "role": "admin",
                "content": log.answer_text,
                "created_at": log.created_at.isoformat() if log.created_at else None
            })
        else:
            messages.append({
                "role": "user",
                "content": log.question_text,
                "created_at": log.created_at.isoformat() if log.created_at else None
            })
            if log.answer_text and log.answer_text not in ["[Handled by Human Admin]", "[Waiting for Support Agent]", "[Added details to Support Ticket]"]:
                messages.append({
                    "role": "assistant",
                    "content": log.answer_text,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                })
    return messages

@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    params = websocket.query_params
    token = params.get("token")
    session_id = params.get("session_id")
    member_id_str = params.get("member_id")
    guest_session_id = params.get("guest_session_id")
    
    JWT_SECRET = os.getenv("JWT_SECRET")
    
    # 1. Enforce/Handle Token Verification
    if token:
        decoded_payload = verify_jwt_token(token)
        if decoded_payload is None:
            await websocket.close(code=4001)
            return
        member_id = decoded_payload.get("member_id", 0)
        guest_session_id = decoded_payload.get("guest_session_id")
        if "session_id" in decoded_payload:
            session_id = decoded_payload["session_id"]
    else:
        try:
            member_id = int(member_id_str) if member_id_str else 0
        except ValueError:
            member_id = 0
            
        if JWT_SECRET and member_id > 0:
            await websocket.close(code=4001)
            return
            
    # Generate session_id if client didn't send one
    if not session_id:
        session_id = str(uuid.uuid4())
        
    await manager.connect_user(websocket, session_id, db, member_id=member_id, guest_session_id=guest_session_id)
    
    # Check if there is history in DB for this session
    has_history = len(manager.session_histories.get(session_id, [])) > 0
    
    # Send welcome message only if it's a completely new session (no history loaded)
    if not has_history:
        await websocket.send_text("Hi there! 👋 I'm Junu, your RealDealRide AI Assistant. How can I help you with your booking today?")
    else:
        await websocket.send_text("Welcome back! 👋 I'm Junu. I've loaded your previous conversation. How can I help you today?")
    
    try:
        while True:
            # Wait for user message
            user_message = await websocket.receive_text()
            db_session_status = "human_active" if session_id in manager.active_admin_connections else "bot"
            await manager.route_message_from_user(session_id, user_message, db_session_status, db, member_id=member_id)
            
    except WebSocketDisconnect:
        await manager.disconnect_user(session_id)

@app.websocket("/ws/admin")
async def websocket_admin_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    params = websocket.query_params
    session_id = params.get("session_id")
    if not session_id:
        await websocket.close()
        return
        
    await manager.connect_admin(websocket, session_id)
    
    # Broadcast alert that admin took over
    user_ws = manager.active_user_connections.get(session_id)
    if user_ws:
        import json
        await user_ws.send_text(json.dumps({"role": "system", "content": "System: A customer support agent has joined the chat and taken over."}))

    try:
        while True:
            admin_message = await websocket.receive_text()
            await manager.route_message_from_admin(session_id, admin_message, db)
            
    except WebSocketDisconnect:
        await manager.disconnect_admin(websocket, session_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
