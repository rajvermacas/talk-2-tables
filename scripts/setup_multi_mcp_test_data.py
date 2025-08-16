#!/usr/bin/env python3
"""
Multi-MCP Test Data Setup

Creates comprehensive test data specifically designed to validate multi-MCP queries.
This ensures Product IDs match between Database MCP and Product Metadata MCP.
"""

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_multi_mcp_test_database():
    """Create a test database with data that links to Product Metadata MCP."""
    
    # Database path
    project_root = Path(__file__).parent.parent
    db_path = project_root / "test_data" / "sample.db"
    
    # Ensure test_data directory exists
    db_path.parent.mkdir(exist_ok=True)
    
    logger.info(f"Creating multi-MCP test database at: {db_path}")
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        
        # Drop existing tables to start fresh
        cursor.execute("DROP TABLE IF EXISTS sales")
        cursor.execute("DROP TABLE IF EXISTS products")
        cursor.execute("DROP TABLE IF EXISTS customers")
        
        # Create customers table
        cursor.execute("""
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                company TEXT
            )
        """)
        
        # Create products table (should match Product MCP data)
        cursor.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                product_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                price REAL
            )
        """)
        
        # Create sales table with foreign keys
        cursor.execute("""
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                product_id TEXT,
                quantity INTEGER,
                amount REAL,
                sale_date DATE,
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)
        
        # Insert test customers
        customers_data = [
            (1, 'John Smith', 'john@techcorp.com', 'TechCorp'),
            (2, 'Sarah Johnson', 'sarah@webdev.io', 'WebDev Inc'),
            (3, 'Mike Chen', 'mike@startupx.com', 'StartupX'),
            (4, 'Lisa Wang', 'lisa@cloudco.com', 'CloudCo'),
            (5, 'David Brown', 'david@innovate.net', 'InnovateLab')
        ]
        
        cursor.executemany(
            "INSERT INTO customers (id, name, email, company) VALUES (?, ?, ?, ?)",
            customers_data
        )
        
        # Insert products that MUST match Product Metadata MCP
        # These product_ids should exist in the Product MCP Server
        products_data = [
            (1, 'axios-001', 'axios', 'HTTP Client', 299.99),
            (2, 'react-001', 'React', 'UI Framework', 499.99),
            (3, 'vue-001', 'Vue', 'UI Framework', 399.99),
            (4, 'lodash-001', 'lodash', 'Utility Library', 199.99),
            (5, 'express-001', 'Express', 'Web Framework', 349.99),
            (6, 'next-001', 'Next.js', 'React Framework', 599.99),
            (7, 'angular-001', 'Angular', 'UI Framework', 549.99),
            (8, 'webpack-001', 'Webpack', 'Build Tool', 249.99)
        ]
        
        cursor.executemany(
            "INSERT INTO products (id, product_id, name, category, price) VALUES (?, ?, ?, ?, ?)",
            products_data
        )
        
        # Insert sales data linking customers to products
        # This data enables cross-MCP queries like "show sales for axios"
        sales_data = [
            # John Smith purchases
            (1, 1, 'axios-001', 2, 599.98, '2024-01-15'),
            (2, 1, 'react-001', 1, 499.99, '2024-01-20'),
            (3, 1, 'lodash-001', 1, 199.99, '2024-02-10'),
            
            # Sarah Johnson purchases  
            (4, 2, 'vue-001', 1, 399.99, '2024-01-18'),
            (5, 2, 'lodash-001', 3, 599.97, '2024-01-22'),
            (6, 2, 'webpack-001', 1, 249.99, '2024-02-15'),
            
            # Mike Chen purchases
            (7, 3, 'axios-001', 1, 299.99, '2024-01-25'),
            (8, 3, 'express-001', 2, 699.98, '2024-01-28'),
            (9, 3, 'next-001', 1, 599.99, '2024-02-01'),
            
            # Lisa Wang purchases
            (10, 4, 'next-001', 1, 599.99, '2024-02-01'),
            (11, 4, 'react-001', 2, 999.98, '2024-02-05'),
            (12, 4, 'angular-001', 1, 549.99, '2024-02-12'),
            
            # David Brown purchases
            (13, 5, 'vue-001', 2, 799.98, '2024-02-20'),
            (14, 5, 'express-001', 1, 349.99, '2024-02-22'),
            (15, 5, 'webpack-001', 2, 499.98, '2024-02-25')
        ]
        
        cursor.executemany(
            "INSERT INTO sales (id, customer_id, product_id, quantity, amount, sale_date) VALUES (?, ?, ?, ?, ?, ?)",
            sales_data
        )
        
        conn.commit()
        
        # Verify data was inserted correctly
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]
        
        logger.info(f"✓ Test database created successfully:")
        logger.info(f"  - Customers: {customer_count}")
        logger.info(f"  - Products: {product_count}")
        logger.info(f"  - Sales: {sales_count}")
        
        # Test critical multi-MCP scenarios
        logger.info("\n🔍 Testing critical multi-MCP query scenarios:")
        
        # Test 1: Sales for specific product (axios)
        cursor.execute("""
            SELECT c.name, p.name, s.quantity, s.amount, s.sale_date
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            JOIN products p ON s.product_id = p.product_id
            WHERE p.product_id = 'axios-001'
        """)
        axios_sales = cursor.fetchall()
        logger.info(f"  - Axios sales records: {len(axios_sales)}")
        for sale in axios_sales:
            logger.info(f"    {sale[0]} bought {sale[2]} units of {sale[1]} for ${sale[3]}")
        
        # Test 2: UI Framework comparison
        cursor.execute("""
            SELECT p.name, SUM(s.quantity) as total_units, SUM(s.amount) as total_revenue
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            WHERE p.category = 'UI Framework'
            GROUP BY p.name
            ORDER BY total_revenue DESC
        """)
        ui_frameworks = cursor.fetchall()
        logger.info(f"  - UI Framework sales comparison:")
        for fw in ui_frameworks:
            logger.info(f"    {fw[0]}: {fw[1]} units, ${fw[2]:.2f} revenue")
        
        # Test 3: Customer purchase history
        cursor.execute("""
            SELECT c.name, p.name, p.category, s.quantity, s.amount
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            JOIN products p ON s.product_id = p.product_id
            WHERE c.name = 'John Smith'
            ORDER BY s.sale_date
        """)
        john_purchases = cursor.fetchall()
        logger.info(f"  - John Smith's purchase history: {len(john_purchases)} items")
        for purchase in john_purchases:
            logger.info(f"    {purchase[1]} ({purchase[2]}) - {purchase[3]} units")

def verify_database_structure():
    """Verify the database structure matches multi-MCP requirements."""
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "test_data" / "sample.db"
    
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return False
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        required_tables = ['customers', 'products', 'sales']
        
        for table in required_tables:
            if table not in tables:
                logger.error(f"Missing required table: {table}")
                return False
        
        # Check critical product IDs that must match Product MCP
        cursor.execute("SELECT product_id FROM products WHERE product_id IN ('axios-001', 'react-001', 'vue-001')")
        critical_products = [row[0] for row in cursor.fetchall()]
        
        if len(critical_products) < 3:
            logger.error("Missing critical product IDs for multi-MCP testing")
            return False
        
        logger.info("✓ Database structure verified for multi-MCP testing")
        return True

if __name__ == "__main__":
    logger.info("Setting up Multi-MCP Test Database")
    logger.info("=" * 50)
    
    create_multi_mcp_test_database()
    
    if verify_database_structure():
        logger.info("\n✅ Multi-MCP test database setup completed successfully!")
        logger.info("Ready for cross-MCP query testing with Product Metadata Server")
    else:
        logger.error("\n❌ Database setup verification failed")
        exit(1)