"""Quick connection check"""
from src.database.connection import db, test_connection, check_database_health
from sqlalchemy import text

print("=" * 60)
print("MYSQL CONNECTION STATUS")
print("=" * 60)

# Test 1: Basic connection
print("\n1. Testing basic connection...")
connected = test_connection()
print(f"   Status: {'[CONNECTED]' if connected else '[NOT CONNECTED]'}")

if connected:
    # Test 2: Query execution
    print("\n2. Testing query execution...")
    try:
        with db.get_session() as session:
            result = session.execute(text("SELECT DATABASE(), VERSION()"))
            row = result.fetchone()
            print(f"   Database: {row[0]}")
            print(f"   MySQL: {row[1][:60]}...")
            print("   [OK] Query successful")
    except Exception as e:
        print(f"   [FAIL] Query failed: {e}")
        connected = False
    
    # Test 3: Health check
    print("\n3. Health check...")
    health = check_database_health()
    print(f"   Connected: {health.get('connected', False)}")
    print(f"   Tables Exist: {health.get('tables_exist', False)}")

print("\n" + "=" * 60)
if connected:
    print("[RESULT] PROJECT IS CONNECTED TO MYSQL")
else:
    print("[RESULT] PROJECT IS NOT CONNECTED TO MYSQL")
print("=" * 60)

