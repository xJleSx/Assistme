"""
Interactive Command Line Interface for Electronics Comparison Platform.
Allows searching, viewing, and comparing products from the database.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.product_service import search_products, get_product_specs, print_product_specs
from services.comparison_service import print_comparison

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    print(f"\n{'=' * 60}")
    print(f" {title.center(58)}")
    print(f"{'=' * 60}\n")

def search_menu():
    """Prompt user for a search query and display results."""
    query = input("\nEnter product name to search (or 'q' to go back): ").strip()
    if not query or query.lower() == 'q':
        return None
        
    results = search_products(query)
    
    if not results:
        print(f"\nNo products found matching '{query}'.")
        return None
        
    print(f"\nFound {len(results)} products:")
    for i, product in enumerate(results, 1):
        print(f"  {i}. {product['brand_name']} {product['name']} ({product['category_name']})")
        
    return results

def view_product_flow():
    """Flow for viewing a single product."""
    print_header("VIEW PRODUCT DETAILS")
    
    while True:
        results = search_menu()
        if not results:
            break
            
        choice = input("\nEnter the number of the product to view (or 'q' to search again): ").strip()
        
        if choice.lower() == 'q':
            continue
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                product_id = results[idx]['id']
                print_product_specs(product_id)
                input("\nPress Enter to continue...")
            else:
                print("Invalid number.")
        except ValueError:
            print("Please enter a valid number.")

def compare_products_flow():
    """Flow for comparing multiple products side-by-side."""
    print_header("COMPARE PRODUCTS")
    
    selected_products = []
    
    while True:
        if selected_products:
            print("\nCurrently selected for comparison:")
            for p in selected_products:
                print(f"  - {p['brand_name']} {p['name']}")
                
            action = input("\nEnter 's' to search for another product, 'c' to compare now, or 'q' to go back: ").strip().lower()
            
            if action == 'q':
                break
            elif action == 'c':
                if len(selected_products) > 1:
                    product_ids = [p['id'] for p in selected_products]
                    print_comparison(product_ids)
                    input("\nPress Enter to continue...")
                else:
                    print("You need at least 2 products to compare.")
                continue
            elif action != 's':
                print("Invalid command.")
                continue
                
        results = search_menu()
        if not results:
            if not selected_products:
                break
            continue
            
        choice = input("\nEnter the number of the product to add to comparison (or 'q' to go back): ").strip()
        
        if choice.lower() == 'q':
            continue
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                product = results[idx]
                # Check if already added
                if any(p['id'] == product['id'] for p in selected_products):
                    print("Product is already in the comparison list.")
                else:
                    selected_products.append(product)
                    print(f"Added {product['brand_name']} {product['name']} to comparison.")
            else:
                print("Invalid number.")
        except ValueError:
            print("Please enter a valid number.")

from services.ai_query_interpreter import interpret_query
from services.query_builder import build_product_query
from services.ranking_engine import rank_products
from services.explanation_service import generate_explanations
from config.db_config import get_session

def ai_search_flow():
    """Flow for AI natural language search."""
    print_header("AI POWERED SEARCH")
    
    while True:
        query = input("\nEnter your search query (e.g. 'best gaming phone under 50000 with big battery') or 'q' to go back: ").strip()
        
        if query.lower() == 'q':
            break
            
        if not query:
            continue
            
        print("\n[AI] Interpreting query...")
        try:
            structured_query = interpret_query(query)
            print(f"  Parsed Intent: {structured_query.model_dump()}")
            
            session = get_session()
            try:
                print("[DB] Executing structured SQL filters...")
                product_ids = build_product_query(session, structured_query)
                print(f"  Found {len(product_ids)} candidate products.")
                
                if not product_ids:
                    print("\nNo products found matching those exact filters. Try loosening your constraints.")
                    continue
                    
                print("[AI] Ranking top products based on specifications and use case...")
                # Rank top 50
                top_ids = product_ids[:50]
                ranked_products = rank_products(top_ids, structured_query.use_case)
                
                top_results = ranked_products[:5]
                print("\n[AI] Generating final recommendations...")
                explanation = generate_explanations(top_results, query)
                
                print_header("RECOMMENDATIONS")
                for i, p in enumerate(top_results, 1):
                    print(f"{i}. {p['brand']} {p['name']} (Score: {p.get('score', 0):.2f})")
                
                print(f"\n[AI Conclusion]:\n{explanation}")
                
            finally:
                session.close()
                
        except Exception as e:
            print(f"Error during AI search: {e}")
            import traceback
            traceback.print_exc()
        
        input("\nPress Enter to continue...")

def main():
    while True:
        clear_screen()
        print_header("ELECTRONICS COMPARISON EXPLORER")
        print("1. View single product details")
        print("2. Compare multiple products")
        print("3. AI Natural Language Search")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            view_product_flow()
        elif choice == '2':
            compare_products_flow()
        elif choice == '3':
            ai_search_flow()
        elif choice == '4':
            print("\nExiting. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()
