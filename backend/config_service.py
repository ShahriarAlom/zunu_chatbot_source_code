import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import AsyncSessionLocal, AiConfiguration

# Global cache to prevent hitting the DB on every message
_cached_config = None
_last_fetch_time = 0
CACHE_TTL = 30 # seconds

DEFAULT_CONFIG = {
    "llm_model": "gemini-3.1-flash-lite",
    "temperature": 0.2,
    "confidence_threshold": 0.70,
    "top_k_chunks": 5,
    "chunk_size_tokens": 350,
    "chunk_overlap_tokens": 75,
    "system_prompt": "You are Zunu, the RealDealRide AI Assistant.\nYou help users book cars, check their reservation status, create support tickets, modify or cancel bookings, look up car reviews/discounts, and answer questions about RealDealRide policies.\n\n{user_status}\n\nSecurity & Authentication Policy:\n- Logged-in members (Securely Authenticated) have full access to view, modify, cancel reservations, and submit support tickets.\n- Anonymous Guests must be authenticated via email before performing account-specific actions. Prompt: \"I'd be happy to help with that! Could you please tell me the email address associated with your account?\"\n- Guests who have verified their email (Dynamically Verified Email) are only allowed to submit support tickets. They are strictly blocked from checking reservation details, modifying reservations, or cancelling reservations due to lack of a secure session token. If they attempt these, the system tool will return a security blocking message. You should explain that they need to log in to the website securely first to perform reservation modifications/viewing.\n\nCore Capabilities:\n- Search and book cars: You can search our live car inventory by city, type (SUV, Sedan, Van, etc.), and price.\n- Check reservation status: You can look up active and past bookings for securely logged-in users.\n- Support tickets: You can open official support tickets directly in our system if a user has an issue.\n- Modify/Cancel Reservations: You can file pending reservation modification requests or cancellation requests for securely logged-in users.\n- Car Reviews & Discounts: You can fetch customer feedback, ratings, and active promotional discounts for specific vehicles.\n- Policy knowledge: You can answer questions about rental rules, age limits, deposits, cancellation policies, etc.\n\nBehavior Guidelines:\n- Be friendly, helpful, clear, and concise.\n- Never invent policies, procedures, reviews, or discounts.\n- When you use the search_car_inventory_tool, check_reservation_status_tool, create_support_ticket_tool, request_reservation_modification_tool, or request_booking_cancellation_tool, the tool will return HTML code for the UI. You MUST return this HTML code EXACTLY as provided without altering it or wrapping it in Markdown blocks. Do not add ```html blocks around the output.\n- If the user asks a conversational question that doesn't require a tool, just answer it directly.",
    "fallback_message": "I want to make sure I give you the right information on that topic. Let me connect you with a member of our support team who can help. One moment please!",
    "escalation_message": "I'd be happy to help with that, but I'll need to connect you with one of our support team members who can access your account details. Hang tight - someone will be with you shortly!",
    "escalation_rate_alert": 20,
    "response_time_alert": 5,
    "email_alerts": True
}

async def get_ai_config() -> dict:
    global _cached_config, _last_fetch_time
    
    current_time = asyncio.get_event_loop().time()
    
    if _cached_config and (current_time - _last_fetch_time < CACHE_TTL):
        return _cached_config
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AiConfiguration).where(AiConfiguration.id == 1))
        db_config = result.scalars().first()
        
        if db_config and db_config.config_data:
            # Merge with defaults in case of missing keys
            merged_config = DEFAULT_CONFIG.copy()
            merged_config.update(db_config.config_data)
            _cached_config = merged_config
        else:
            _cached_config = DEFAULT_CONFIG
            
        _last_fetch_time = current_time
        return _cached_config

async def update_ai_config(new_config: dict):
    global _cached_config, _last_fetch_time
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AiConfiguration).where(AiConfiguration.id == 1))
        db_config = result.scalars().first()
        
        if db_config:
            # Merge with existing
            current_data = db_config.config_data or {}
            current_data.update(new_config)
            db_config.config_data = current_data
        else:
            db_config = AiConfiguration(id=1, config_data=new_config)
            session.add(db_config)
            
        await session.commit()
        
        # Invalidate cache immediately
        _cached_config = None
        _last_fetch_time = 0

async def ensure_default_config(session: AsyncSession):
    """Called on startup to ensure table has at least one row."""
    # Ensure table exists
    from database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    result = await session.execute(select(AiConfiguration).where(AiConfiguration.id == 1))
    db_config = result.scalars().first()
    
    if not db_config:
        print("Seeding default AI configuration to database...")
        db_config = AiConfiguration(id=1, config_data=DEFAULT_CONFIG)
        session.add(db_config)
        await session.commit()
