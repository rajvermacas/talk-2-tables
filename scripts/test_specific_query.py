#!/usr/bin/env python3
"""
Test the specific query that was generated.
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_query():
    """Test the specific query that was generated."""
    
    try:
        conn = sqlite3.connect('test_data/sample.db')
        cursor = conn.cursor()
        
        # Test the exact query that was generated
        query = "SELECT DISTINCT category FROM products"
        logger.info(f"Testing query: {query}")
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        logger.info(f"Query returned {len(results)} rows")
        logger.info(f"Results: {results}")
        
        # Check the column name
        cursor.execute("PRAGMA table_info(products);")
        columns = cursor.fetchall()
        logger.info(f"Products table columns: {columns}")
        
        # Try with a different approach
        cursor.execute("SELECT * FROM products LIMIT 3;")
        sample_data = cursor.fetchall()
        logger.info(f"Sample products data: {sample_data}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error testing query: {str(e)}")

if __name__ == "__main__":
    test_query()