-- Initialize database schema for visual search project

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(255),
    price DECIMAL(10, 2),
    currency VARCHAR(10),
    image_url TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for products
CREATE INDEX IF NOT EXISTS idx_products_external_id ON products(external_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at);

-- Create search logs table
CREATE TABLE IF NOT EXISTS search_logs (
    id SERIAL PRIMARY KEY,
    query_type VARCHAR(50) NOT NULL,
    query_text TEXT,
    query_image_url TEXT,
    results_count INTEGER,
    execution_time_ms INTEGER,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for search logs
CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON search_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_query_type ON search_logs(query_type);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for products table
DROP TRIGGER IF EXISTS update_products_updated_at ON products;
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

