-- =============================================================================
--  RealDealRide AI Q&A System — MariaDB 11.7+ Vector Database Schema
--
--  WHAT CHANGED FROM THE MySQL 9.0 VERSION:
--    ✓ Native VECTOR INDEX (HNSW) inline in CREATE TABLE — no plugins
--    ✓ Built-in VEC_DISTANCE_COSINE() — no custom stored functions
--    ✓ VEC_FromText() replaces STRING_TO_VECTOR()
--    ✓ VEC_ToText() replaces VECTOR_TO_STRING()
--    ✓ Removed embedding_hnsw mirror column (HNSW indexes VECTOR directly)
--    ✓ Removed all 4 stored functions (~80 lines of code eliminated)
--    ✓ Cleaner, faster, simpler
--
--  Embedding Dimensions:
--    Demo/Test  → VECTOR(8)    (32 bytes per chunk — portable testing)
--    Production → VECTOR(1536) (6,144 bytes — OpenAI ada-002)
--
--  IMPORTANT: Change VECTOR(8) → VECTOR(1536) for production.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS realdealride_ai
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE realdealride_ai;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 1 — KNOWLEDGE BASE DOCUMENT MANAGEMENT                        ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- 1.1  Document Categories
CREATE TABLE kb_categories (
    category_id       INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    category_name     VARCHAR(100)    NOT NULL UNIQUE,
    description       TEXT            NULL,
    priority_boost    DECIMAL(4,2)    NOT NULL DEFAULT 0.00
                      COMMENT 'Score bonus added during retrieval (0.00–0.50)',
    color_hex         CHAR(7)         NOT NULL DEFAULT '#2E75B6',
    is_active         TINYINT(1)      NOT NULL DEFAULT 1,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_cat_active (is_active)
) ENGINE=InnoDB;


-- 1.2  Knowledge Base Documents
CREATE TABLE kb_documents (
    document_id       INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    category_id       INT UNSIGNED    NOT NULL,
    title             VARCHAR(255)    NOT NULL,
    file_name         VARCHAR(255)    NOT NULL,
    file_size_bytes   BIGINT UNSIGNED NOT NULL DEFAULT 0,
    file_hash_sha256  CHAR(64)        NULL COMMENT 'SHA-256 of the original PDF',
    cloudflare_r2_key VARCHAR(500)    NOT NULL COMMENT 'Object key in R2 bucket',
    version           VARCHAR(20)     NOT NULL DEFAULT '1.0',
    effective_date    DATE            NULL,
    page_count        SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    status            ENUM('uploading','processing','active','archived','error')
                      NOT NULL DEFAULT 'uploading',
    error_message     TEXT            NULL,
    source_text       LONGTEXT        NULL,
    uploaded_by       VARCHAR(255)    NOT NULL DEFAULT 'admin@realdealride.com',
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_doc_category
        FOREIGN KEY (category_id) REFERENCES kb_categories(category_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    INDEX idx_doc_status   (status),
    INDEX idx_doc_category (category_id),
    INDEX idx_doc_version  (title, version)
) ENGINE=InnoDB;


-- 1.3  Document Tags (Many-to-Many)
CREATE TABLE kb_tags (
    tag_id            INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    tag_name          VARCHAR(50)     NOT NULL UNIQUE,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE kb_document_tags (
    document_id       INT UNSIGNED    NOT NULL,
    tag_id            INT UNSIGNED    NOT NULL,

    PRIMARY KEY (document_id, tag_id),

    CONSTRAINT fk_doctag_doc
        FOREIGN KEY (document_id) REFERENCES kb_documents(document_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_doctag_tag
        FOREIGN KEY (tag_id) REFERENCES kb_tags(tag_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;


-- 1.4  Document Version History
CREATE TABLE kb_document_versions (
    version_id        INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    document_id       INT UNSIGNED    NOT NULL,
    version           VARCHAR(20)     NOT NULL,
    cloudflare_r2_key VARCHAR(500)    NOT NULL,
    file_hash_sha256  CHAR(64)        NULL,
    is_active         TINYINT(1)      NOT NULL DEFAULT 0,
    change_notes      TEXT            NULL,
    created_by        VARCHAR(255)    NOT NULL,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_docver_doc
        FOREIGN KEY (document_id) REFERENCES kb_documents(document_id)
        ON DELETE CASCADE ON UPDATE CASCADE,

    INDEX idx_docver_active (document_id, is_active)
) ENGINE=InnoDB;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 2 — VECTOR EMBEDDINGS (Core of RAG Pipeline)                   ║
-- ║                                                                         ║
-- ║  MariaDB 11.7+ Native Features:                                         ║
-- ║    • VECTOR(n) data type with 32-bit IEEE 754 floats                    ║
-- ║    • VECTOR INDEX with built-in HNSW algorithm                          ║
-- ║    • DISTANCE=cosine for semantic text search                           ║
-- ║    • M parameter controls HNSW graph connectivity                       ║
-- ║    • Index is maintained automatically on INSERT/UPDATE/DELETE           ║
-- ║    • All transaction isolation levels supported                         ║
-- ║    • No plugins, no mirror columns, no manual rebuilds                  ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- 2.1  Document Chunks with Vector Embeddings + Native HNSW Index
--
--  ┌──────────────────────────────────────────────────────────────────┐
--  │  VECTOR(8)   = 8-dimensional demo embedding  (32 bytes)        │
--  │  VECTOR(1536)= production ada-002 embedding  (6,144 bytes)     │
--  │                                                                │
--  │  VECTOR INDEX = Native MariaDB HNSW — auto-built, auto-       │
--  │                 maintained, sub-millisecond ANN search          │
--  │                                                                │
--  │  Change VECTOR(8) → VECTOR(1536) for production.              │
--  └──────────────────────────────────────────────────────────────────┘
--
CREATE TABLE kb_chunk_embeddings (
    chunk_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id       INT UNSIGNED    NOT NULL,
    chunk_index       SMALLINT UNSIGNED NOT NULL
                      COMMENT 'Sequential position within the document (0-based)',
    chunk_text        TEXT            NOT NULL
                      COMMENT 'The actual text content of this chunk',
    token_count       SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    section_title     VARCHAR(255)    NULL
                      COMMENT 'Nearest heading/section in the source PDF',

    -- ═══ THE VECTOR COLUMN + NATIVE HNSW INDEX ═══
    -- MariaDB 11.7+ VECTOR data type
    -- VECTOR INDEX creates a built-in HNSW graph — no plugins needed!
    embedding         VECTOR(768)       NOT NULL
                      COMMENT 'Embedding vector — VECTOR(768) for gemini-embedding-001',

    embedding_model   VARCHAR(100)    NOT NULL DEFAULT 'text-embedding-ada-002',
    is_active         TINYINT(1)      NOT NULL DEFAULT 1,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_chunk_doc
        FOREIGN KEY (document_id) REFERENCES kb_documents(document_id)
        ON DELETE CASCADE ON UPDATE CASCADE,

    -- ═══ NATIVE HNSW VECTOR INDEX ═══
    -- M=6: HNSW graph connectivity (higher = more accurate, more memory)
    -- DISTANCE=cosine: optimized for text embeddings
    -- Index is built and maintained automatically on every write!
    VECTOR INDEX idx_chunk_embedding (embedding) M=6 DISTANCE=cosine,

    INDEX idx_chunk_doc       (document_id, chunk_index),
    INDEX idx_chunk_active    (is_active, document_id),
    INDEX idx_chunk_section   (section_title)
) ENGINE=InnoDB;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 3 — NO STORED FUNCTIONS NEEDED!                                ║
-- ║                                                                         ║
-- ║  MariaDB 11.7+ includes these built-in C-level functions:               ║
-- ║    • VEC_DISTANCE_COSINE(v1, v2)  → cosine distance (0–2, lower=better)║
-- ║    • VEC_DISTANCE_EUCLIDEAN(v1,v2)→ L2 distance (lower=better)         ║
-- ║    • VEC_DISTANCE(v1, v2)         → auto-selects based on index type   ║
-- ║    • VEC_FromText('[...]')        → converts JSON array to VECTOR       ║
-- ║    • VEC_ToText(col)              → converts VECTOR to readable string  ║
-- ║                                                                         ║
-- ║  The 4 custom MySQL functions (vec_dot_product, vec_norm,               ║
-- ║  vec_cosine_similarity, vec_cosine_distance) are NOT needed.            ║
-- ║  ~80 lines of stored function code eliminated.                          ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 4 — QUERY & CONVERSATION MANAGEMENT                           ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- 4.1  Chat Sessions
CREATE TABLE chat_sessions (
    session_id        CHAR(36)        PRIMARY KEY COMMENT 'UUID v4',
    member_id         INT UNSIGNED    NOT NULL,
    platform          ENUM('web','ios','android') NOT NULL DEFAULT 'web',
    started_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at          TIMESTAMP       NULL,
    total_messages    SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    was_escalated     TINYINT(1)      NOT NULL DEFAULT 0,
    satisfaction_score TINYINT UNSIGNED NULL COMMENT '1–5 star rating',

    INDEX idx_sess_member    (member_id),
    INDEX idx_sess_started   (started_at),
    INDEX idx_sess_escalated (was_escalated)
) ENGINE=InnoDB;


-- 4.2  Individual Query Log
CREATE TABLE query_log (
    query_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id        CHAR(36)        NOT NULL,
    member_id         INT UNSIGNED    NOT NULL,

    -- The question
    question_text     TEXT            NOT NULL,
    question_embedding VECTOR(768)      NULL
                      COMMENT 'Embedding of the question for audit/replay',

    -- Classification
    intent_class      ENUM('policy','howto','account_specific','general','out_of_scope')
                      NULL,
    detected_language VARCHAR(10)     NOT NULL DEFAULT 'en',

    -- Retrieval metrics
    top_chunk_ids     JSON            NULL COMMENT 'Array of matched chunk_ids',
    top_similarity    DECIMAL(5,4)    NULL COMMENT 'Highest similarity score',
    chunks_retrieved  TINYINT UNSIGNED NOT NULL DEFAULT 0,

    -- Generation
    answer_text       TEXT            NULL,
    confidence_score  DECIMAL(5,4)    NULL,
    response_time_ms  INT UNSIGNED    NULL,

    -- Outcome
    was_fallback      TINYINT(1)      NOT NULL DEFAULT 0,
    was_escalated     TINYINT(1)      NOT NULL DEFAULT 0,
    source_documents  JSON            NULL COMMENT 'Array of {document_id, section}',
    member_feedback   ENUM('helpful','not_helpful') NULL,

    -- PII safety
    pii_detected      TINYINT(1)      NOT NULL DEFAULT 0,
    pii_redacted_text TEXT            NULL,

    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_query_session
        FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
        ON DELETE CASCADE ON UPDATE CASCADE,

    INDEX idx_query_member     (member_id),
    INDEX idx_query_intent     (intent_class),
    INDEX idx_query_confidence (confidence_score),
    INDEX idx_query_fallback   (was_fallback),
    INDEX idx_query_created    (created_at)
) ENGINE=InnoDB;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 5 — ESCALATION TRACKING                                        ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE escalations (
    escalation_id     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    query_id          BIGINT UNSIGNED NOT NULL,
    session_id        CHAR(36)        NOT NULL,
    member_id         INT UNSIGNED    NOT NULL,

    trigger_reason    ENUM('low_confidence','explicit_request','account_specific','frustration_detected')
                      NOT NULL,
    agent_id          INT UNSIGNED    NULL COMMENT 'Support agent who handled it',
    context_snapshot  JSON            NOT NULL COMMENT 'Full conversation + chunks at escalation time',
    estimated_wait_s  INT UNSIGNED    NULL,
    resolved_at       TIMESTAMP       NULL,
    resolution_notes  TEXT            NULL,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_esc_query
        FOREIGN KEY (query_id) REFERENCES query_log(query_id)
        ON DELETE CASCADE ON UPDATE CASCADE,

    INDEX idx_esc_trigger  (trigger_reason),
    INDEX idx_esc_created  (created_at),
    INDEX idx_esc_agent    (agent_id)
) ENGINE=InnoDB;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 6 — SYSTEM CONFIGURATION                                       ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- 6.1  System Configuration (Key-Value)
CREATE TABLE system_config (
    config_key        VARCHAR(100)    PRIMARY KEY,
    config_value      TEXT            NOT NULL,
    value_type        ENUM('string','number','boolean','json') NOT NULL DEFAULT 'string',
    description       VARCHAR(500)    NULL,
    updated_by        VARCHAR(255)    NOT NULL DEFAULT 'system',
    updated_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- 6.2  Prompt Templates with Version History
CREATE TABLE prompt_templates (
    template_id       INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    template_key      VARCHAR(50)     NOT NULL COMMENT 'system_prompt | fallback_message | escalation_message',
    template_text     TEXT            NOT NULL,
    version           INT UNSIGNED    NOT NULL DEFAULT 1,
    is_active         TINYINT(1)      NOT NULL DEFAULT 1,
    created_by        VARCHAR(255)    NOT NULL,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_template_version (template_key, version),
    INDEX idx_template_active (template_key, is_active)
) ENGINE=InnoDB;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 7 — ANALYTICS / AGGREGATED METRICS                             ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE daily_metrics (
    metric_date       DATE            NOT NULL,
    total_queries     INT UNSIGNED    NOT NULL DEFAULT 0,
    answered_queries  INT UNSIGNED    NOT NULL DEFAULT 0,
    fallback_queries  INT UNSIGNED    NOT NULL DEFAULT 0,
    escalated_queries INT UNSIGNED    NOT NULL DEFAULT 0,
    avg_confidence    DECIMAL(5,4)    NULL,
    avg_response_ms   INT UNSIGNED    NULL,
    p95_response_ms   INT UNSIGNED    NULL,
    avg_satisfaction  DECIMAL(3,2)    NULL,

    PRIMARY KEY (metric_date)
) ENGINE=InnoDB;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 8 — ADMIN / AUDIT                                              ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE admin_users (
    admin_id          INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    email             VARCHAR(255)    NOT NULL UNIQUE,
    display_name      VARCHAR(100)    NOT NULL,
    role              ENUM('super_admin','admin','viewer') NOT NULL DEFAULT 'admin',
    password_hash     VARCHAR(255)    NOT NULL,
    is_active         TINYINT(1)      NOT NULL DEFAULT 1,
    last_login_at     TIMESTAMP       NULL,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE audit_log (
    audit_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    admin_id          INT UNSIGNED    NULL,
    action            VARCHAR(50)     NOT NULL
                      COMMENT 'document_uploaded | document_archived | config_changed | prompt_updated',
    target_type       VARCHAR(50)     NULL,
    target_id         VARCHAR(100)    NULL,
    details           JSON            NULL,
    ip_address        VARCHAR(45)     NULL,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_audit_admin  (admin_id),
    INDEX idx_audit_action (action),
    INDEX idx_audit_created(created_at)
) ENGINE=InnoDB;


SET FOREIGN_KEY_CHECKS = 1;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 9 — SAMPLE SEED DATA                                           ║
-- ║                                                                         ║
-- ║  Uses VEC_FromText() — MariaDB's native vector insertion function.       ║
-- ║  8-dimensional demo embeddings crafted for semantic clustering.          ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- ─── 9.1 Categories ─────────────────────────────────────────────────────────
INSERT INTO kb_categories (category_id, category_name, description, priority_boost, color_hex) VALUES
(1, 'Trip Extras',       'Optional add-ons: gear, conveniences, and services',      0.10, '#2E75B6'),
(2, 'Protection Plans',  'Vehicle protection, liability, and insurance coverage',    0.05, '#28A745'),
(3, 'Cancellation',      'Cancellation policies, refund rules, and penalties',       0.08, '#F59E0B'),
(4, 'Vehicle Standards', 'Vehicle eligibility, mileage, age, and condition rules',   0.00, '#17A2B8'),
(5, 'Account FAQ',       'Billing, receipts, account management, and support',       0.00, '#DC3545');


-- ─── 9.2 Documents ──────────────────────────────────────────────────────────
INSERT INTO kb_documents (document_id, category_id, title, file_name, file_size_bytes, cloudflare_r2_key, version, effective_date, page_count, status, uploaded_by) VALUES
(1, 1, 'Trip Extras Policy',              'trip_extras_v1.2.pdf',        245760,  'kb/trip-extras/v1.2/trip_extras_v1.2.pdf',       '1.2', '2026-05-02', 2,  'active',     'admin@realdealride.com'),
(2, 2, 'Protection Plans Guide',           'protection_plans_v3.0.pdf',  1048576, 'kb/protection/v3.0/protection_plans_v3.0.pdf',   '3.0', '2026-04-28', 8,  'active',     'admin@realdealride.com'),
(3, 3, 'Cancellation & Refund Policy',     'cancellation_v2.1.pdf',      512000,  'kb/cancellation/v2.1/cancellation_v2.1.pdf',     '2.1', '2026-04-20', 4,  'active',     'admin@realdealride.com'),
(4, 4, 'Vehicle Standards & Requirements', 'vehicle_standards_v2.1.pdf',  768000, 'kb/vehicle/v2.1/vehicle_standards_v2.1.pdf',     '2.1', '2026-04-15', 5,  'processing', 'admin@realdealride.com'),
(5, 5, 'Account & Billing FAQ',            'account_faq_v1.0.pdf',       384000,  'kb/account/v1.0/account_faq_v1.0.pdf',           '1.0', '2026-04-10', 3,  'active',     'admin@realdealride.com');


-- ─── 9.3 Tags ───────────────────────────────────────────────────────────────
INSERT INTO kb_tags (tag_id, tag_name) VALUES
(1, 'refuel'),     (2, 'car-seat'),   (3, 'pet-fee'),
(4, 'bike-rack'),  (5, 'gear'),       (6, 'protection'),
(7, 'liability'),  (8, 'cancellation'),(9, 'refund'),
(10,'mileage'),    (11,'billing'),    (12,'receipt');

INSERT INTO kb_document_tags (document_id, tag_id) VALUES
(1,1),(1,2),(1,3),(1,4),(1,5),
(2,6),(2,7),
(3,8),(3,9),
(4,10),
(5,11),(5,12);




-- Chunks deleted



-- ─── 9.5 System Configuration ───────────────────────────────────────────────
INSERT INTO system_config (config_key, config_value, value_type, description) VALUES
('confidence_threshold',    '0.70',                          'number',  'Minimum similarity score before fallback is triggered'),
('top_k_chunks',            '5',                             'number',  'Number of top chunks to retrieve per query'),
('chunk_size_tokens',       '350',                           'number',  'Target chunk size in tokens'),
('chunk_overlap_tokens',    '75',                            'number',  'Overlap between consecutive chunks in tokens'),
('embedding_model',         'text-embedding-ada-002',        'string',  'Model used for generating embeddings'),
('embedding_dimensions',    '1536',                          'number',  'Dimension of production embedding vectors'),
('llm_provider',            'anthropic',                     'string',  'Primary LLM provider'),
('llm_model',               'claude-sonnet-4-20250514',  'string',  'LLM model identifier'),
('llm_temperature',         '0.2',                           'number',  'LLM temperature setting'),
('llm_max_tokens',          '500',                           'number',  'Maximum response tokens'),
('escalation_rate_alert',   '20',                            'number',  'Alert threshold for escalation rate percentage'),
('response_time_alert_ms',  '5000',                          'number',  'Alert threshold for response time in ms'),
('query_log_retention_days','90',                             'number',  'Days to retain query logs before purge'),
('enable_pii_redaction',    'true',                          'boolean', 'Whether to strip PII before sending to LLM'),
('enable_multilanguage',    'true',                          'boolean', 'Whether multi-language detection is active'),
('supported_languages',     '["en","es"]',                   'json',    'Array of supported language codes'),
('vector_index_m',          '6',                             'number',  'HNSW M parameter (graph connectivity)'),
('vector_distance_metric',  'cosine',                        'string',  'Distance metric for VECTOR INDEX');


-- ─── 9.6 Prompt Templates ───────────────────────────────────────────────────
INSERT INTO prompt_templates (template_key, template_text, version, is_active, created_by) VALUES
('system_prompt',
'You are the RealDealRide AI Assistant, helping Members with questions about our peer-to-peer car rental platform.\n\nRULES:\n- ONLY answer based on the provided knowledge base context\n- If the context does not contain the answer, use the fallback message\n- Be friendly, helpful, clear, and concise\n- Never invent policies, fees, percentages, or procedures\n- Never use legal jargon or overly technical language\n- Always cite the source document when answering\n- If the Member asks about their specific account, billing, or personal trip details, escalate to a human agent\n\nTONE: Conversational, warm, and professional.',
 4, 1, 'admin@realdealride.com'),

('fallback_message',
'I want to make sure I give you the right information on that topic. Let me connect you with a member of our support team who can help. One moment please!',
 3, 1, 'admin@realdealride.com'),

('escalation_message',
'I''d be happy to help with that, but I''ll need to connect you with one of our support team members who can access your account details. Hang tight — someone will be with you shortly!',
 2, 1, 'admin@realdealride.com');


-- ─── 9.7 Sample Chat Sessions & Queries ─────────────────────────────────────
INSERT INTO chat_sessions (session_id, member_id, platform, started_at, total_messages, was_escalated, satisfaction_score) VALUES
('a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d', 1001, 'web',     '2026-05-04 09:15:00', 3, 0, 5),
('b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e', 1002, 'ios',     '2026-05-04 09:22:00', 2, 0, 4),
('c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f', 1003, 'android', '2026-05-04 10:05:00', 4, 1, 3),
('d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a', 1004, 'web',     '2026-05-04 11:30:00', 1, 0, 5);

INSERT INTO query_log (query_id, session_id, member_id, question_text, intent_class, top_chunk_ids, top_similarity, chunks_retrieved, answer_text, confidence_score, response_time_ms, was_fallback, was_escalated, source_documents) VALUES
(1, 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d', 1001,
 'Can I add a car seat after I already booked my trip?',
 'howto', '[2, 1, 4]', 0.9400, 3,
 'Yes! You can add any available Extras in the RealDealRide app as long as your trip hasn''t started yet. Just go to "Manage Trip" and look for the "Extras" section.',
 0.9400, 1823, 0, 0, '[{"document_id":1,"section":"How to Add or Remove Extras"}]'),

(2, 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d', 1001,
 'What if my trip already started?',
 'howto', '[2, 5]', 0.8800, 2,
 'Once your trip has started, most physical gear like car seats can''t be added. However, you can message the Owner directly to ask about adding a service like a pet fee.',
 0.8800, 2105, 0, 0, '[{"document_id":1,"section":"How to Add or Remove Extras"}]'),

(3, 'b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e', 1002,
 'I paid for Prepaid Refuel. Do I still need to fill up the tank?',
 'policy', '[4, 1]', 0.9200, 2,
 'Nope! With the Prepaid Refuel Extra, you can return the car at any fuel level. The Owner will take care of the refilling for you.',
 0.9200, 1650, 0, 0, '[{"document_id":1,"section":"Popular Extras & Rules"}]'),

(4, 'c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f', 1003,
 'What is the cancellation penalty if I cancel 2 hours before pickup?',
 'policy', '[11, 12]', 0.8500, 2,
 'Cancellations within 24 hours of the trip start time are subject to a fee equal to the cost of one day of the reservation.',
 0.8500, 2340, 0, 0, '[{"document_id":3,"section":"Cancellation Windows"}]'),

(5, 'c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f', 1003,
 'Where is my refund? I cancelled last week!',
 'account_specific', NULL, NULL, 0,
 NULL, 0.2500, 890, 1, 1, NULL),

(6, 'd4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a', 1004,
 'The bike rack I rented from the Owner broke. Does my protection plan cover it?',
 'policy', '[6, 9, 8]', 0.9100, 3,
 'Unfortunately, RealDealRide protection plans only cover the vehicle itself, not Extras. You''ll need to coordinate with the Owner to resolve the cost of the damaged rack.',
 0.9100, 1980, 0, 0, '[{"document_id":1,"section":"Protection & Liability"},{"document_id":2,"section":"What Protection Covers"}]');


-- ─── 9.8 Sample Escalation ──────────────────────────────────────────────────
INSERT INTO escalations (query_id, session_id, member_id, trigger_reason, context_snapshot, estimated_wait_s) VALUES
(5, 'c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f', 1003, 'account_specific',
 '{"messages":[{"role":"user","text":"What is the cancellation penalty if I cancel 2 hours before pickup?"},{"role":"ai","text":"Cancellations within 24 hours..."},{"role":"user","text":"Where is my refund? I cancelled last week!"}],"ai_confidence":0.25}',
 120);


-- ─── 9.9 Sample Daily Metrics ───────────────────────────────────────────────
INSERT INTO daily_metrics VALUES
('2026-04-21', 320, 286, 28, 34, 0.8200, 2400, 4800, 4.30),
('2026-04-22', 410, 368, 32, 42, 0.8350, 2300, 4600, 4.40),
('2026-04-23', 385, 345, 30, 40, 0.8280, 2350, 4700, 4.35),
('2026-04-24', 480, 432, 35, 48, 0.8400, 2200, 4500, 4.50),
('2026-04-25', 520, 470, 38, 50, 0.8450, 2150, 4400, 4.55),
('2026-04-26', 390, 351, 30, 39, 0.8300, 2300, 4650, 4.40),
('2026-04-27', 445, 401, 33, 44, 0.8380, 2250, 4550, 4.45),
('2026-04-28', 510, 462, 36, 48, 0.8420, 2180, 4450, 4.52),
('2026-04-29', 470, 424, 35, 46, 0.8390, 2220, 4500, 4.48),
('2026-04-30', 530, 480, 37, 50, 0.8460, 2100, 4350, 4.58),
('2026-05-01', 490, 443, 35, 47, 0.8410, 2190, 4480, 4.50),
('2026-05-02', 560, 508, 38, 52, 0.8480, 2080, 4300, 4.60),
('2026-05-03', 610, 555, 40, 55, 0.8520, 2020, 4200, 4.65),
('2026-05-04', 580, 527, 39, 53, 0.8500, 2050, 4250, 4.62);


-- ─── 9.10 Admin Users ───────────────────────────────────────────────────────
INSERT INTO admin_users (email, display_name, role, password_hash) VALUES
('admin@realdealride.com', 'Admin User', 'super_admin', '$2b$12$placeholder_hash_for_demo'),
('qa@realdealride.com',    'QA Tester',  'admin',       '$2b$12$placeholder_hash_for_demo');


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  SECTION 10 — SEMANTIC SEARCH QUERIES (MariaDB 11.7+ Native)            ║
-- ║                                                                         ║
-- ║  All queries use built-in VEC_DISTANCE_COSINE() + VECTOR INDEX.         ║
-- ║  The HNSW index is used automatically when you ORDER BY VEC_DISTANCE.   ║
-- ║  No plugins. No stored functions. No manual index builds.               ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝


-- ─── 10.1 Views (using MariaDB native functions) ────────────────────────────

-- View: Document summary with chunk counts
CREATE OR REPLACE VIEW v_document_summary AS
SELECT
    d.document_id,
    d.title,
    d.version,
    d.status,
    cat.category_name,
    d.page_count,
    COUNT(ce.chunk_id) AS total_chunks,
    SUM(ce.token_count) AS total_tokens,
    d.created_at,
    d.updated_at
FROM kb_documents d
LEFT JOIN kb_categories cat ON cat.category_id = d.category_id
LEFT JOIN kb_chunk_embeddings ce ON ce.document_id = d.document_id AND ce.is_active = 1
GROUP BY d.document_id;

-- View: Query performance summary (last 30 days)
CREATE OR REPLACE VIEW v_query_performance AS
SELECT
    DATE(created_at) AS query_date,
    COUNT(*) AS total_queries,
    SUM(was_fallback) AS fallback_count,
    SUM(was_escalated) AS escalated_count,
    ROUND(AVG(confidence_score), 4) AS avg_confidence,
    ROUND(AVG(response_time_ms)) AS avg_response_ms,
    ROUND(SUM(was_escalated) / COUNT(*) * 100, 1) AS escalation_pct
FROM query_log
WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DATE(created_at)
ORDER BY query_date DESC;

-- View: Top unanswered questions
CREATE OR REPLACE VIEW v_top_unanswered AS
SELECT
    question_text,
    COUNT(*) AS times_asked,
    ROUND(AVG(confidence_score), 4) AS avg_confidence,
    MAX(created_at) AS last_asked
FROM query_log
WHERE was_fallback = 1
GROUP BY question_text
ORDER BY times_asked DESC
LIMIT 20;


-- ═══════════════════════════════════════════════════════════════════════════
--  DONE! MariaDB 11.7+ schema created with sample data.
--
--  ┌────────────────────────────────────────────────────────────────────┐
--  │  QUICK VERIFICATION QUERIES                                       │
--  │                                                                    │
--  │  -- Check chunks loaded                                           │
--  │  SELECT COUNT(*) AS total_chunks FROM kb_chunk_embeddings;         │
--  │  -- Expected: 14                                                   │
--  │                                                                    │
--  │  -- Document summary                                              │
--  │  SELECT * FROM v_document_summary;                                │
--  │                                                                    │
--  │  -- Test HNSW vector search: "Can I add extras after booking?"    │
--  │  SELECT                                                           │
--  │      ce.chunk_id,                                                 │
--  │      d.title,                                                     │
--  │      ce.section_title,                                            │
--  │      ROUND(1 - VEC_DISTANCE_COSINE(                              │
--  │          ce.embedding,                                            │
--  │          VEC_FromText('[0.91,0.84,0.14,0.07,0.86,0.04,0.16,0.09]')│
--  │      ), 4) AS similarity                                         │
--  │  FROM kb_chunk_embeddings ce                                      │
--  │  JOIN kb_documents d ON d.document_id = ce.document_id            │
--  │  WHERE ce.is_active = 1                                           │
--  │  ORDER BY VEC_DISTANCE_COSINE(                                    │
--  │      ce.embedding,                                                │
--  │      VEC_FromText('[0.91,0.84,0.14,0.07,0.86,0.04,0.16,0.09]')   │
--  │  ) ASC                                                            │
--  │  LIMIT 5;                                                         │
--  │                                                                    │
--  │  -- Verify HNSW index exists                                      │
--  │  SHOW INDEX FROM kb_chunk_embeddings                              │
--  │  WHERE Index_type = 'VECTOR';                                     │
--  │                                                                    │
--  │  -- View daily analytics                                          │
--  │  SELECT * FROM daily_metrics ORDER BY metric_date DESC LIMIT 7;   │
--  └────────────────────────────────────────────────────────────────────┘
-- ═══════════════════════════════════════════════════════════════════════════
