import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Boolean, ForeignKey, Enum, JSON, Numeric, BigInteger, SmallInteger
from sqlalchemy.sql import func
from dotenv import load_dotenv

load_dotenv()

import urllib.parse

# We use aiomysql for asynchronous MariaDB connectivity
def get_mariadb_uri():
    uri = os.getenv("MARIADB_URI")
    if uri:
        return uri
    # Try reading individual components
    host = os.getenv("CHATBOT_DB_HOST", "localhost")
    port = os.getenv("CHATBOT_DB_PORT", "3306")
    username = os.getenv("CHATBOT_DB_USERNAME", "root")
    password = os.getenv("CHATBOT_DB_PASSWORD", "password")
    database = os.getenv("CHATBOT_DB_DATABASE", "realdealride_ai")
    
    quoted_password = urllib.parse.quote_plus(password) if password else ""
    return f"mysql+aiomysql://{username}:{quoted_password}@{host}:{port}/{database}"

DATABASE_URL = get_mariadb_uri()
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

# --- CHAT SESSIONS & QUERY LOGS ---

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id = Column(String(36), primary_key=True)
    member_id = Column(Integer, nullable=False)
    platform = Column(Enum('web', 'ios', 'android'), default='web')
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    total_messages = Column(SmallInteger, default=0)
    was_escalated = Column(Boolean, default=False)
    satisfaction_score = Column(SmallInteger, nullable=True)

class QueryLog(Base):
    __tablename__ = "query_log"

    query_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey('chat_sessions.session_id', ondelete='CASCADE'), nullable=False)
    member_id = Column(Integer, nullable=False)
    
    question_text = Column(Text, nullable=False)
    # Note: question_embedding is stored as VECTOR in MariaDB. We map it as String for ORM reading (using VEC_ToText) if needed.
    
    intent_class = Column(Enum('policy', 'howto', 'account_specific', 'general', 'out_of_scope'), nullable=True)
    detected_language = Column(String(10), default='en')
    
    top_chunk_ids = Column(JSON, nullable=True)
    top_similarity = Column(Numeric(5, 4), nullable=True)
    chunks_retrieved = Column(SmallInteger, default=0)
    
    answer_text = Column(Text, nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    was_fallback = Column(Boolean, default=False)
    was_escalated = Column(Boolean, default=False)
    source_documents = Column(JSON, nullable=True)
    member_feedback = Column(Enum('helpful', 'not_helpful'), nullable=True)
    
    pii_detected = Column(Boolean, default=False)
    pii_redacted_text = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())

# --- ESCALATION / SUPPORT TICKETS ---

class Escalation(Base):
    __tablename__ = "escalations"

    escalation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_id = Column(BigInteger, ForeignKey('query_log.query_id', ondelete='CASCADE'), nullable=False)
    session_id = Column(String(36), ForeignKey('chat_sessions.session_id', ondelete='CASCADE'), nullable=False)
    member_id = Column(Integer, nullable=False)
    
    trigger_reason = Column(Enum('low_confidence', 'explicit_request', 'account_specific', 'frustration_detected'), nullable=False)
    agent_id = Column(Integer, nullable=True)
    context_snapshot = Column(JSON, nullable=False)
    estimated_wait_s = Column(Integer, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

# --- KNOWLEDGE BASE ---

class KbCategory(Base):
    __tablename__ = "kb_categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    priority_boost = Column(Numeric(4, 2), default=0.00)
    color_hex = Column(String(7), default='#2E75B6')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class KbDocument(Base):
    __tablename__ = "kb_documents"

    document_id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('kb_categories.category_id'), nullable=False)
    title = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, default=0)
    file_hash_sha256 = Column(String(64), nullable=True)
    cloudflare_r2_key = Column(String(500), nullable=False)
    version = Column(String(20), default='1.0')
    status = Column(Enum('uploading', 'processing', 'active', 'archived', 'error'), default='uploading')
    source_text = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class KbChunkEmbedding(Base):
    __tablename__ = "kb_chunk_embeddings"

    chunk_id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('kb_documents.document_id', ondelete='CASCADE'), nullable=False)
    chunk_index = Column(SmallInteger, nullable=False)
    chunk_text = Column(Text, nullable=False)
    token_count = Column(SmallInteger, default=0)
    section_title = Column(String(255), nullable=True)
    
    # We will primarily interact with 'embedding' using raw SQL queries with VEC_FromText()
    embedding_model = Column(String(100), default='text-embedding-ada-002')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

# --- DAILY METRICS / ANALYTICS ---

class DailyMetrics(Base):
    __tablename__ = "daily_metrics"

    metric_date = Column(Date, primary_key=True)
    total_queries = Column(Integer, default=0)
    answered_queries = Column(Integer, default=0)
    fallback_queries = Column(Integer, default=0)
    escalated_queries = Column(Integer, default=0)
    avg_confidence = Column(Numeric(5, 4), nullable=True)
    avg_response_ms = Column(Integer, nullable=True)
    p95_response_ms = Column(Integer, nullable=True)
    avg_satisfaction = Column(Numeric(3, 2), nullable=True)

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

