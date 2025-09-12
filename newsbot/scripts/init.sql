-- Database initialization script for NewsBot
-- This script sets up initial database configuration

-- Set timezone for the session
SET timezone = 'America/Mexico_City';

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Create indexes for better performance with Spanish text
-- These will be useful for search functionality

-- Function to create case-insensitive indexes for Spanish text
CREATE OR REPLACE FUNCTION create_spanish_search_index(table_name text, column_name text)
RETURNS void AS $$
BEGIN
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_%s_spanish 
                   ON %s USING gin(to_tsvector(''spanish'', %s))',
                   table_name, column_name, table_name, column_name);
END;
$$ LANGUAGE plpgsql;

-- Insert initial configuration data if tables exist
-- This will be executed after the Python models create the tables

-- Note: The actual table creation is handled by SQLAlchemy/Alembic
-- This script only contains database-specific setup