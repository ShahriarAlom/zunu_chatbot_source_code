import os
import asyncio
from typing import Dict, List
from fastapi import WebSocket
from ai_engine import generate_bot_response
from sqlalchemy.ext.asyncio import AsyncSession
from database import ChatSession, QueryLog

class ConnectionManager:
    def __init__(self):
        # Maps session_id to the user's WebSocket connection
        self.active_user_connections: Dict[str, WebSocket] = {}
        # Maps session_id to the admin's WebSocket connection (if taken over)
        self.active_admin_connections: Dict[str, WebSocket] = {}
        # A list of admin WebSockets listening to the global queue
        self.global_admins: List[WebSocket] = []
        # Store chat memory per session
        self.session_histories: Dict[str, list] = {}
        # Maps session_id to state ('bot', 'pending_human', 'human_active', 'ticket_fallback')
        self.session_states: Dict[str, str] = {}
        # Maps session_id to asyncio timeout tasks
        self.timeout_tasks: Dict[str, asyncio.Task] = {}

    async def connect_user(self, websocket: WebSocket, session_id: str, db: AsyncSession, member_id: int = 0, guest_session_id: str = None):
        """Accepts a user connection, registers them, merges guest session if needed, and loads history."""
        await websocket.accept()
        self.active_user_connections[session_id] = websocket
        
        # 1. Merge Guest History if member_id is logged in (> 0) and guest_session_id is provided
        if member_id > 0 and guest_session_id:
            from sqlalchemy import update, delete
            try:
                # Find if the guest session exists in DB and get its member_id
                res_guest_sess = await db.execute(select(ChatSession).where(ChatSession.session_id == guest_session_id))
                guest_sess = res_guest_sess.scalars().first()
                guest_member_id = guest_sess.member_id if guest_sess else 0
                
                if guest_session_id != session_id:
                    # Update all QueryLog entries from the guest session to the new logged-in session and member ID
                    await db.execute(
                        update(QueryLog)
                        .where(QueryLog.session_id == guest_session_id)
                        .values(member_id=member_id, session_id=session_id)
                    )
                    
                    # Delete the old empty guest session in DB to prevent duplicates
                    if guest_sess:
                        await db.execute(
                            delete(ChatSession)
                            .where(ChatSession.session_id == guest_session_id)
                        )
                    print(f"Merged guest session {guest_session_id} into logged-in user {member_id} / session {session_id}")
                else:
                    # If guest_session_id is equal to session_id, we just update the QueryLogs for this session
                    await db.execute(
                        update(QueryLog)
                        .where(QueryLog.session_id == session_id)
                        .values(member_id=member_id)
                    )
                
                # Merge support tickets from guest user ID to the logged-in user ID
                if guest_member_id > 0 and guest_member_id != member_id:
                    from operational_api import merge_guest_support_tickets
                    await merge_guest_support_tickets(guest_member_id, member_id)
                    
                await db.commit()
            except Exception as e:
                await db.rollback()
                print(f"Error merging guest session and support tickets: {e}")

        # 2. Check if ChatSession already exists
        from sqlalchemy import select
        result = await db.execute(select(ChatSession).where(ChatSession.session_id == session_id))
        db_session = result.scalars().first()
        
        if db_session:
            # Enforce that guest or other users cannot hijack an authenticated user's session if JWT_SECRET is configured
            if os.getenv("JWT_SECRET") and db_session.member_id > 0 and db_session.member_id != member_id:
                await websocket.close(code=4001)
                if session_id in self.active_user_connections:
                    del self.active_user_connections[session_id]
                return False
                
        if not db_session:
            # Create a new session in DB
            db_session = ChatSession(
                session_id=session_id,
                member_id=member_id,
                platform='web',
                total_messages=0
            )
            db.add(db_session)
            try:
                await db.commit()
            except Exception as e:
                await db.rollback()
                print(f"Error creating session: {e}")
        else:

            # If session exists but member_id changed (e.g. guest logged in)
            if db_session.member_id != member_id:
                # Store the old member_id to merge support tickets if necessary
                old_member_id = db_session.member_id
                db_session.member_id = member_id
                
                # Update all QueryLogs for this session to have the new member_id
                await db.execute(
                    update(QueryLog)
                    .where(QueryLog.session_id == session_id)
                    .values(member_id=member_id)
                )
                
                # Merge support tickets from old guest member_id to the new member_id
                if old_member_id > 0 and old_member_id != member_id:
                    from operational_api import merge_guest_support_tickets
                    await merge_guest_support_tickets(old_member_id, member_id)
                    
                try:
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    print(f"Error updating session member_id: {e}")

            # Re-initialize state if it was escalated in the database but no active admin is connected
            if db_session.was_escalated:
                if session_id not in self.active_admin_connections:
                    # Let them fallback or wait depending on timeout
                    self.session_states[session_id] = "pending_human"
                    await self.set_session_state_pending(session_id, db, member_id)

        # 3. Load Chat History from DB into in-memory chat memory
        result = await db.execute(
            select(QueryLog)
            .where(QueryLog.session_id == session_id)
            .order_by(QueryLog.created_at.asc())
        )
        rows = result.scalars().all()
        history = []
        for row in rows:
            if row.question_text == "[Admin Response]":
                history.append({"role": "assistant", "content": row.answer_text})
            else:
                history.append({"role": "user", "content": row.question_text})
                if row.answer_text and row.answer_text != "[Handled by Human Admin]":
                    history.append({"role": "assistant", "content": row.answer_text})
        
        # Keep only the last 10 messages
        self.session_histories[session_id] = history[-10:]
        return True

    async def disconnect_user(self, session_id: str):
        """Removes a user connection."""
        if session_id in self.active_user_connections:
            del self.active_user_connections[session_id]
        # Clean up timeout task if any
        if session_id in self.timeout_tasks:
            self.timeout_tasks[session_id].cancel()
            del self.timeout_tasks[session_id]

    async def connect_admin(self, websocket: WebSocket, session_id: str = None):
        """
        Accepts an admin connection.
        If session_id is provided, they are taking over a specific chat.
        If not, they are connecting to the global queue to listen for alerts.
        """
        await websocket.accept()
        if session_id:
            self.active_admin_connections[session_id] = websocket
            self.session_states[session_id] = "human_active"
            
            # Cancel the timeout task since the admin has connected
            if session_id in self.timeout_tasks:
                self.timeout_tasks[session_id].cancel()
                del self.timeout_tasks[session_id]
                print(f"Admin connected to session {session_id}. Timeout task cancelled.")
        else:
            self.global_admins.append(websocket)

    async def disconnect_admin(self, websocket: WebSocket, session_id: str = None):
        """Removes an admin connection."""
        if session_id and session_id in self.active_admin_connections:
            del self.active_admin_connections[session_id]
            # Reset state back to bot if the admin disconnected
            self.session_states[session_id] = "bot"
            
            # Notify the user
            user_ws = self.active_user_connections.get(session_id)
            if user_ws:
                import json
                await user_ws.send_text(json.dumps({"role": "system", "content": "System: The support agent has left the chat. Routing back to AI..."}))
        elif websocket in self.global_admins:
            self.global_admins.remove(websocket)

    async def set_session_state_pending(self, session_id: str, db: AsyncSession, member_id: int):
        """Transitions a session into pending_human state and schedules the fallback timeout."""
        self.session_states[session_id] = "pending_human"
        
        # Cancel existing timeout task if any
        if session_id in self.timeout_tasks:
            self.timeout_tasks[session_id].cancel()
            
        # Get timeout value from env or default to 300 seconds (5 minutes)
        timeout_seconds = int(os.getenv("ADMIN_TIMEOUT_SECONDS", "300"))
        
        # Schedule the timeout task
        self.timeout_tasks[session_id] = asyncio.create_task(
            self.handle_admin_timeout(session_id, db, member_id, timeout_seconds)
        )
        print(f"Scheduled non-response timeout check ({timeout_seconds}s) for session {session_id}")

    async def handle_admin_timeout(self, session_id: str, db: AsyncSession, member_id: int, timeout_seconds: int):
        """Checks if an admin connected within the timeout period; if not, triggers the support ticket fallback."""
        try:
            await asyncio.sleep(timeout_seconds)
            
            # If the session is still waiting for a human after the timeout
            if self.session_states.get(session_id) == "pending_human":
                self.session_states[session_id] = "ticket_fallback"
                
                # Send fallback notification to the user's widget
                user_ws = self.active_user_connections.get(session_id)
                if user_ws:
                    fallback_msg = (
                        "System: Our support agents are currently busy or offline. "
                        "We have automatically created a support ticket for you. If you would "
                        "like to add any other details about this issue, please type them below "
                        "and we will append them to your ticket."
                    )
                    import json
                    await user_ws.send_text(json.dumps({"role": "system", "content": fallback_msg}))
                print(f"Session {session_id} timed out waiting for admin. Switched to ticket_fallback.")
        except asyncio.CancelledError:
            pass # Task was cancelled because admin took over or user disconnected

    async def route_message_from_user(self, session_id: str, message: str, db_session_status: str, db: AsyncSession, member_id: int = 0):
        """
        Traffic Controller: Routes the user's message based on connection state and logs to DB.
        """
        # Prepare the query log entry
        query_log = QueryLog(
            session_id=session_id,
            member_id=member_id,
            question_text=message,
            detected_language='en'
        )
        
        # Resolve session state
        current_state = self.session_states.get(session_id, "bot")
        
        # Override with active admin connection if they connected
        if session_id in self.active_admin_connections:
            current_state = "human_active"
            
        if current_state == "human_active":
            # Route directly to the assigned admin
            admin_ws = self.active_admin_connections.get(session_id)
            if admin_ws:
                await admin_ws.send_text(message)
                query_log.answer_text = "[Handled by Human Admin]"
                
                # Append user message to in-memory history so AI knows what happened if admin disconnects
                history = self.session_histories.get(session_id, [])
                history.append({"role": "user", "content": message})
                self.session_histories[session_id] = history[-10:]
            else:
                # Fallback if admin disconnected abruptly
                user_ws = self.active_user_connections.get(session_id)
                if user_ws:
                    import json
                    await user_ws.send_text(json.dumps({"role": "system", "content": "System: The admin disconnected. Routing back to AI..."}))
                    # Fallback to AI
                    self.session_states[session_id] = "bot"
                    history = self.session_histories.get(session_id, [])
                    bot_reply = await generate_bot_response(message, db, history, member_id=member_id, session_id=session_id)
                    await user_ws.send_text(json.dumps({"role": "assistant", "content": bot_reply}))
                    
                    # Update history
                    history.append({"role": "user", "content": message})
                    history.append({"role": "assistant", "content": bot_reply})
                    self.session_histories[session_id] = history[-10:]
                    
                    query_log.answer_text = bot_reply
                    query_log.was_fallback = True
                    
        elif current_state == "pending_human":
            # User is waiting for admin to join. Show waiting notification
            user_ws = self.active_user_connections.get(session_id)
            if user_ws:
                import json
                await user_ws.send_text(json.dumps({"role": "system", "content": "System: Please wait while we connect you to a support agent..."}))
            query_log.answer_text = "[Waiting for Support Agent]"
            
            # Log the message to history so admin takeover can see it
            history = self.session_histories.get(session_id, [])
            history.append({"role": "user", "content": message})
            self.session_histories[session_id] = history[-10:]
            
        elif current_state == "ticket_fallback":
            # Admin not available fallback: Append message to their latest support ticket
            from operational_api import append_to_latest_support_ticket
            await append_to_latest_support_ticket(member_id, message)
            
            user_ws = self.active_user_connections.get(session_id)
            if user_ws:
                import json
                await user_ws.send_text(json.dumps({"role": "system", "content": "System: Thank you! We have added this detail to your support ticket. An agent will get back to you shortly."}))
            query_log.answer_text = "[Added details to Support Ticket]"
            
            # Append fallback messages to history
            history = self.session_histories.get(session_id, [])
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": "[Added details to Support Ticket]"})
            self.session_histories[session_id] = history[-10:]
            
        else:
            # Standard Route: Route to the AI Pipeline (bot state)
            history = self.session_histories.get(session_id, [])
            bot_reply = await generate_bot_response(message, db, history, member_id=member_id, session_id=session_id)
            
            # Update history
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": bot_reply})
            self.session_histories[session_id] = history[-10:]
            
            user_ws = self.active_user_connections.get(session_id)
            if user_ws:
                # Normal bot responses can be sent directly as text or styled normally, 
                # but to make the widget consistent we will send them as text (which it falls back to)
                await user_ws.send_text(bot_reply)
            query_log.answer_text = bot_reply
            
        # Commit the query log
        db.add(query_log)
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"Error saving query log: {e}")

    async def route_message_from_admin(self, session_id: str, message: str, db: AsyncSession):
        """Routes a message from an admin directly to the specific user and logs to database."""
        user_ws = self.active_user_connections.get(session_id)
        if user_ws:
            import json
            payload = json.dumps({"role": "admin", "content": message})
            await user_ws.send_text(payload)
            
        # Append admin message to in-memory history so AI knows what happened if admin disconnects
        history = self.session_histories.get(session_id, [])
        history.append({"role": "assistant", "content": message})
        self.session_histories[session_id] = history[-10:]
            
        # Log admin reply in query_log as [Admin Response]
        member_id = 0
        try:
            from sqlalchemy import select
            result = await db.execute(select(ChatSession.member_id).where(ChatSession.session_id == session_id))
            member_id = result.scalar() or 0
        except Exception as e:
            print(f"Error looking up member_id for admin message logging: {e}")
            
        query_log = QueryLog(
            session_id=session_id,
            member_id=member_id,
            question_text="[Admin Response]",
            answer_text=message,
            detected_language='en'
        )
        db.add(query_log)
        try:
            await db.commit()
            print(f"Saved admin reply in query_log for session {session_id}")
        except Exception as e:
            await db.rollback()
            print(f"Error saving admin reply log: {e}")

    async def broadcast_to_admins(self, message: str):
        """Broadcasts a global alert (e.g. 'User needs human help') to all queue-watching admins."""
        for admin_ws in self.global_admins:
            await admin_ws.send_text(message)

manager = ConnectionManager()
