#!/usr/bin/env python3
"""Script to create and populate a test SQLite database.

This script creates a sample database with realistic business data for 
testing the Talk 2 Tables MCP server functionality.
"""

import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# Sample data for generating realistic test records
FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Edward", "Fiona", "George", "Hannah",
    "Ian", "Julia", "Kevin", "Laura", "Michael", "Nina", "Oliver", "Petra",
    "Quinn", "Rachel", "Samuel", "Tara", "Ulrich", "Victoria", "William", "Xara",
    "Yann", "Zoe", "Alex", "Beth", "Chris", "Debra", "Ethan", "Grace"
]

LAST_NAMES = [
    "Anderson", "Brown", "Clark", "Davis", "Evans", "Fisher", "Garcia", "Harris",
    "Johnson", "King", "Lewis", "Miller", "Nelson", "O'Connor", "Parker", "Quinn",
    "Rodriguez", "Smith", "Taylor", "Underwood", "Williams", "Young", "Zhang",
    "Adams", "Baker", "Cooper", "Dixon", "Edwards", "Foster", "Green", "Hill"
]

COUNTRIES = [
    "United States", "Canada", "United Kingdom", "Germany", "France", 
    "Australia", "Japan", "Netherlands", "Sweden", "Switzerland"
]

CITIES = {
    "United States": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "United Kingdom": ["London", "Manchester", "Birmingham", "Liverpool", "Bristol"],
    "Germany": ["Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt"],
    "France": ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"],
    "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "Japan": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya"],
    "Netherlands": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven"],
    "Sweden": ["Stockholm", "Gothenburg", "Malmö", "Uppsala", "Linköping"],
    "Switzerland": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne"]
}

PRODUCT_CATEGORIES = [
    "Electronics", "Clothing", "Home & Garden", "Sports", "Books", 
    "Health & Beauty", "Toys", "Automotive", "Food & Beverages", "Office Supplies"
]

PRODUCT_NAMES = {
    "Electronics": ["Smartphone", "Laptop", "Tablet", "Headphones", "Camera", "TV", "Speaker"],
    "Clothing": ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Dress", "Sweater", "Hat"],
    "Home & Garden": ["Lamp", "Chair", "Table", "Plant", "Cushion", "Mirror", "Vase"],
    "Sports": ["Tennis Racket", "Football", "Yoga Mat", "Dumbbells", "Running Shoes", "Bicycle"],
    "Books": ["Novel", "Textbook", "Cookbook", "Biography", "Comic Book", "Dictionary"],
    "Health & Beauty": ["Shampoo", "Moisturizer", "Vitamin", "Toothbrush", "Perfume"],
    "Toys": ["Board Game", "Puzzle", "Action Figure", "Doll", "Building Blocks"],
    "Automotive": ["Car Battery", "Oil Filter", "Tire", "Car Cover", "GPS Device"],
    "Food & Beverages": ["Coffee", "Tea", "Snacks", "Juice", "Energy Bar"],
    "Office Supplies": ["Pen", "Notebook", "Stapler", "Calculator", "Desk Organizer"]
}

SUPPLIERS = [
    "Global Electronics Co.", "Fashion Forward Inc.", "Home Comfort Ltd.", 
    "Sports World Corp.", "Book Paradise", "Beauty Essentials", "Toy Factory",
    "Auto Parts Plus", "Fresh Foods Co.", "Office Solutions Inc."
]

ORDER_STATUSES = ["pending", "shipped", "delivered", "cancelled"]


def create_database_schema(conn: sqlite3.Connection) -> None:
    """Create the database schema with all required tables.
    
    Args:
        conn: SQLite database connection
    """
    print("Creating database schema...")
    
    # Create customers table
    conn.execute('''
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            address TEXT,
            city TEXT,
            country TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create products table
    conn.execute('''
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            supplier TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create orders table
    conn.execute('''
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date DATE NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            shipping_address TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
    ''')
    
    # Create order_items table
    conn.execute('''
        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (order_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        )
    ''')
    
    # Create indexes for better query performance
    conn.execute('CREATE INDEX idx_customers_email ON customers (email)')
    conn.execute('CREATE INDEX idx_orders_customer_id ON orders (customer_id)')
    conn.execute('CREATE INDEX idx_orders_date ON orders (order_date)')
    conn.execute('CREATE INDEX idx_order_items_order_id ON order_items (order_id)')
    conn.execute('CREATE INDEX idx_order_items_product_id ON order_items (product_id)')
    conn.execute('CREATE INDEX idx_products_category ON products (category)')
    
    conn.commit()
    print("Database schema created successfully.")


def generate_customers(conn: sqlite3.Connection, num_customers: int = 100) -> List[int]:
    """Generate and insert customer data.
    
    Args:
        conn: SQLite database connection
        num_customers: Number of customers to generate
        
    Returns:
        List of customer IDs
    """
    print(f"Generating {num_customers} customers...")
    
    customers = []
    used_emails = set()
    
    for i in range(num_customers):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        
        # Generate unique email
        email_base = f"{first_name.lower()}.{last_name.lower()}"
        email = f"{email_base}@example.com"
        counter = 1
        while email in used_emails:
            email = f"{email_base}{counter}@example.com"
            counter += 1
        used_emails.add(email)
        
        country = random.choice(COUNTRIES)
        city = random.choice(CITIES[country])
        
        # Some customers might not have phone/address
        phone = f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}" if random.random() > 0.2 else None
        address = f"{random.randint(1, 999)} {random.choice(['Main St', 'Oak Ave', 'Elm St', 'Pine Rd'])}" if random.random() > 0.15 else None
        
        # Random creation date in the past year
        days_ago = random.randint(0, 365)
        created_at = datetime.now() - timedelta(days=days_ago)
        
        cursor = conn.execute('''
            INSERT INTO customers (first_name, last_name, email, phone, address, city, country, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (first_name, last_name, email, phone, address, city, country, created_at))
        
        customers.append(cursor.lastrowid)
    
    conn.commit()
    print(f"Generated {len(customers)} customers.")
    return customers


def generate_products(conn: sqlite3.Connection, num_products: int = 50) -> List[int]:
    """Generate and insert product data.
    
    Args:
        conn: SQLite database connection
        num_products: Number of products to generate
        
    Returns:
        List of product IDs
    """
    print(f"Generating {num_products} products...")
    
    products = []
    
    for i in range(num_products):
        category = random.choice(PRODUCT_CATEGORIES)
        base_name = random.choice(PRODUCT_NAMES[category])
        
        # Add some variation to product names
        variations = ["Pro", "Deluxe", "Premium", "Standard", "Classic", "2024", "V2"]
        name = f"{base_name} {random.choice(variations)}" if random.random() > 0.3 else base_name
        
        description = f"High-quality {base_name.lower()} for {category.lower()} enthusiasts."
        
        # Price based on category
        price_ranges = {
            "Electronics": (50, 2000),
            "Clothing": (20, 200),
            "Home & Garden": (15, 500),
            "Sports": (25, 300),
            "Books": (10, 50),
            "Health & Beauty": (5, 100),
            "Toys": (10, 80),
            "Automotive": (20, 500),
            "Food & Beverages": (3, 30),
            "Office Supplies": (5, 100)
        }
        
        min_price, max_price = price_ranges[category]
        price = round(random.uniform(min_price, max_price), 2)
        
        stock_quantity = random.randint(0, 100)
        supplier = random.choice(SUPPLIERS)
        
        # Random creation date
        days_ago = random.randint(0, 365)
        created_at = datetime.now() - timedelta(days=days_ago)
        
        cursor = conn.execute('''
            INSERT INTO products (name, description, category, price, stock_quantity, supplier, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, category, price, stock_quantity, supplier, created_at))
        
        products.append(cursor.lastrowid)
    
    conn.commit()
    print(f"Generated {len(products)} products.")
    return products


def generate_orders_and_items(conn: sqlite3.Connection, customer_ids: List[int], 
                             product_ids: List[int], num_orders: int = 200) -> None:
    """Generate and insert order and order item data.
    
    Args:
        conn: SQLite database connection
        customer_ids: List of available customer IDs
        product_ids: List of available product IDs
        num_orders: Number of orders to generate
    """
    print(f"Generating {num_orders} orders...")
    
    for i in range(num_orders):
        customer_id = random.choice(customer_ids)
        
        # Random order date in the past 6 months
        days_ago = random.randint(0, 180)
        order_date = (datetime.now() - timedelta(days=days_ago)).date()
        
        status = random.choice(ORDER_STATUSES)
        
        # Get customer address for shipping
        customer_info = conn.execute(
            'SELECT address, city, country FROM customers WHERE customer_id = ?',
            (customer_id,)
        ).fetchone()
        
        if customer_info and customer_info[0]:  # If customer has address
            shipping_address = f"{customer_info[0]}, {customer_info[1]}, {customer_info[2]}"
        else:
            shipping_address = f"{random.randint(1, 999)} Default St, Default City, Default Country"
        
        # Create order first (we'll update total_amount later)
        order_cursor = conn.execute('''
            INSERT INTO orders (customer_id, order_date, total_amount, status, shipping_address)
            VALUES (?, ?, ?, ?, ?)
        ''', (customer_id, order_date, 0.0, status, shipping_address))
        
        order_id = order_cursor.lastrowid
        
        # Generate 1-5 items per order
        num_items = random.randint(1, 5)
        total_amount = 0.0
        
        for j in range(num_items):
            product_id = random.choice(product_ids)
            quantity = random.randint(1, 3)
            
            # Get product price
            product_price = conn.execute(
                'SELECT price FROM products WHERE product_id = ?',
                (product_id,)
            ).fetchone()[0]
            
            unit_price = float(product_price)
            
            conn.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            ''', (order_id, product_id, quantity, unit_price))
            
            total_amount += quantity * unit_price
        
        # Update order total
        conn.execute(
            'UPDATE orders SET total_amount = ? WHERE order_id = ?',
            (round(total_amount, 2), order_id)
        )
    
    conn.commit()
    print(f"Generated {num_orders} orders with items.")


def create_test_database(db_path: str, num_customers: int = 100, 
                        num_products: int = 50, num_orders: int = 200) -> None:
    """Create a complete test database with sample data.
    
    Args:
        db_path: Path where the database should be created
        num_customers: Number of customers to generate
        num_products: Number of products to generate
        num_orders: Number of orders to generate
    """
    print(f"Creating test database at: {db_path}")
    
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database if it exists
    if Path(db_path).exists():
        Path(db_path).unlink()
        print("Removed existing database.")
    
    # Create and populate database
    with sqlite3.connect(db_path) as conn:
        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')
        
        # Create schema
        create_database_schema(conn)
        
        # Generate data
        customer_ids = generate_customers(conn, num_customers)
        product_ids = generate_products(conn, num_products)
        generate_orders_and_items(conn, customer_ids, product_ids, num_orders)
    
    print(f"Test database created successfully at: {db_path}")
    print(f"Database contains:")
    print(f"  - {num_customers} customers")
    print(f"  - {num_products} products")
    print(f"  - {num_orders} orders with multiple items each")


def main():
    """Main function to create the test database."""
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    db_path = project_root / "test_data" / "sample.db"
    
    try:
        create_test_database(str(db_path))
        print("\nTest database setup completed successfully!")
        print(f"You can now run the MCP server with: python -m talk_2_tables_mcp.server")
        
    except Exception as e:
        print(f"Error creating test database: {e}")
        raise


if __name__ == "__main__":
    main()