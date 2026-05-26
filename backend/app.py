import os
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from socket_manager import manager

app = FastAPI(title="RealDealRide AI Chatbot API")

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
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve list of past sessions for a member or a list of session IDs (for guest histories).
    """
    from sqlalchemy import select
    from database import ChatSession, QueryLog
    
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
async def get_chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve full chronological message log for a session.
    """
    from sqlalchemy import select
    from database import QueryLog
    
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
    session_id = params.get("session_id")
    member_id_str = params.get("member_id")
    guest_session_id = params.get("guest_session_id")
    
    # Generate session_id if client didn't send one
    if not session_id:
        session_id = str(uuid.uuid4())
        
    try:
        member_id = int(member_id_str) if member_id_str else 0
    except ValueError:
        member_id = 0
        
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
