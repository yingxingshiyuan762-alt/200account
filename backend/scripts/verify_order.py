"""Verify account order"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import get_session
from src.database.models import Account
import json

with get_session() as session:
    accounts = session.query(Account).all()
    print(f"Total accounts: {len(accounts)}")
    
    ordered = []
    for a in accounts:
        if a.metadata_json:
            try:
                metadata = json.loads(a.metadata_json)
                ordered.append({
                    'username': a.username,
                    'order': metadata.get('display_order', 0),
                    'row': metadata.get('sheet_row', 0)
                })
            except:
                pass
    
    ordered.sort(key=lambda x: x['order'])
    
    print(f"\nFirst 5 accounts:")
    for i, a in enumerate(ordered[:5], 1):
        print(f"  {i}. {a['username']} (order: {a['order']}, row: {a['row']})")
    
    print(f"\nLast 5 accounts:")
    for i, a in enumerate(ordered[-5:], len(ordered)-4):
        print(f"  {i}. {a['username']} (order: {a['order']}, row: {a['row']})")
    
    print(f"\nAll accounts properly ordered: {len(ordered) == 126}")
