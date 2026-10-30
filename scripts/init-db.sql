-- Morning Intelligence Assistant - Database Initialization
-- Run on first database creation

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for better performance
-- (These will be created by SQLAlchemy, but we can add additional ones here)

-- User settings table already has primary key on user_id
-- Briefing records have index on date and status
-- Delivery attempts have index on briefing_id and status, plus unique on idempotency_key
-- Run status has indexes on started_at and status

-- Additional useful indexes
CREATE INDEX IF NOT EXISTS idx_briefing_records_delivery_status ON briefing_records(delivery_status);
CREATE INDEX IF NOT EXISTS idx_delivery_attempts_created_at ON delivery_attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_run_status_run_type ON run_status(run_type);

-- Grant permissions (if using a dedicated user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO morning_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO morning_user;