#!/usr/bin/env python3
"""
Check if database has data.
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database():
    """Check database tables and data."""
    
    try:
        conn = sqlite3.connect('test_data/sample.db')
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logger.info(f"Tables in database: {[table[0] for table in tables]}")
        
        # Check each table's data
        for table_tuple in tables:
            table_name = table_tuple[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            logger.info(f"Table '{table_name}' has {count} rows")
            
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                rows = cursor.fetchall()
                logger.info(f"Sample data from '{table_name}': {rows}")
        
        # Specifically check categories table
        logger.info("Checking categories table structure...")
        cursor.execute("PRAGMA table_info(categories);")
        columns = cursor.fetchall()
        logger.info(f"Categories table columns: {columns}")
        
        cursor.execute("SELECT * FROM categories;")
        categories_data = cursor.fetchall()
        logger.info(f"All categories data: {categories_data}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error checking database: {str(e)}")

if __name__ == "__main__":
    check_database()