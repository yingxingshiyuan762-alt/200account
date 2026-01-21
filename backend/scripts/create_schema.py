"""
Create Database Schema Script

Executes mysql_schema.sql to create all required tables
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "backend"))

from src.database.connection import get_session
from sqlalchemy import text
from src.core.logger import logger

def create_schema():
    """Execute mysql_schema.sql to create database tables"""
    try:
        schema_path = project_root / "database" / "mysql_schema.sql"
        
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            return False
        
        logger.info(f"Reading schema file: {schema_path}")
        sql_content = schema_path.read_text(encoding='utf-8')
        
        # Split SQL into statements - handle multi-line statements properly
        # Remove comments first
        lines = []
        for line in sql_content.split('\n'):
            stripped = line.strip()
            # Skip comment-only lines
            if stripped.startswith('--') and not stripped.startswith('-- ═'):
                continue
            # Skip empty lines
            if not stripped:
                continue
            lines.append(line)
        
        # Join all lines and split by semicolon
        full_sql = '\n'.join(lines)
        # Split by semicolon, but keep the semicolon
        raw_statements = full_sql.split(';')
        statements = []
        
        for stmt in raw_statements:
            stmt = stmt.strip()
            if stmt and not stmt.upper().startswith('SELECT'):
                # Add semicolon back
                statements.append(stmt + ';')
        
        # Execute statements
        logger.info(f"Executing {len(statements)} SQL statements...")
        
        with get_session() as session:
            executed = 0
            for i, statement in enumerate(statements, 1):
                try:
                    session.execute(text(statement))
                    executed += 1
                    if i % 5 == 0:
                        logger.info(f"Executed {i}/{len(statements)} statements...")
                except Exception as e:
                    error_msg = str(e).lower()
                    # Ignore "already exists" errors
                    if 'already exists' in error_msg or 'duplicate' in error_msg:
                        logger.debug(f"Statement {i}: {e} (ignored)")
                    else:
                        logger.warning(f"Statement {i} warning: {e}")
            
            session.commit()
        logger.info(f"Schema created successfully! ({executed} statements executed)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create schema: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Creating Database Schema")
    print("=" * 60)
    print()
    
    success = create_schema()
    
    if success:
        print("\nDatabase schema created successfully!")
        sys.exit(0)
    else:
        print("\nFailed to create schema. Please check the error messages above.")
        sys.exit(1)
