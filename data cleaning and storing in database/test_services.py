import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.comparison_service import print_comparison, rank_by_use_case
from config.db_config import get_session
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.ERROR)
session = get_session()

print('\n--- Comparison Test ---')
# Get 3 top tier mobiles
rows = session.execute(text('''
    SELECT p.id, p.name FROM products p 
    WHERE p.category_id = (SELECT id FROM categories WHERE slug = 'mobile')
    AND p.name IN ('iPhone 16 Pro Max', 'Galaxy S25 Ultra', '14 Ultra')
    LIMIT 3
''')).fetchall()

pids = [r[0] for r in rows]

if len(pids) > 0:
    print_comparison(pids)
    
    print('\n--- Ranking Test (Camera) ---')
    rankings = rank_by_use_case(pids, 'camera')
    for r in rankings:
        print(f'{r["score"]:.2f} - {r["brand"]} {r["name"]}')
        cam_mp = r["details"].get("camera_mp", {}).get("value", "N/A")
        print(f'   Camera MP: {cam_mp}')
else:
    print('Could not find those specific models. Trying random ones.')
    rows = session.execute(text('''
        SELECT p.id, p.name FROM products p 
        WHERE p.category_id = (SELECT id FROM categories WHERE slug = 'mobile')
        LIMIT 3
    ''')).fetchall()
    pids = [r[0] for r in rows]
    print_comparison(pids)
    
    print('\n--- Ranking Test (Battery Life) ---')
    rankings = rank_by_use_case(pids, 'battery_life')
    for r in rankings:
        print(f'{r["score"]:.2f} - {r["brand"]} {r["name"]}')
        bat = r["details"].get("battery_capacity", {}).get("value", "N/A")
        print(f'   Battery: {bat} mAh')
