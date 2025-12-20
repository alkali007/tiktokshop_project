import json

files = {
    "electronics": "electronics_data.json",
    "beauty": "beauty_data.json"
}

# This will store: { "Product Name": ["electronics", "beauty"] }
product_registry = {}
# This will store the actual data: { "Product Name": {item_data} }
product_data_store = {}

# --- PASS 1: SCAN BOTH FILES ---
for category, filename in files.items():
    try:
        with open(filename, 'r') as f:
            items = json.load(f)
            for item in items:
                name = item.get('name', '').strip()
                if not name: continue
                
                # Track which categories this name appears in
                if name not in product_registry:
                    product_registry[name] = []
                    product_data_store[name] = item
                
                if category not in product_registry[name]:
                    product_registry[name].append(category)
    except FileNotFoundError:
        print(f"File {filename} not found.")

# --- PASS 2: ORGANIZE BASED ON SCAN ---
final_output = {
    "electronics": [],
    "beauty": [],
    "conflicts": [] # Items found in BOTH files (the leaks)
}

for name, categories in product_registry.items():
    item_data = product_data_store[name]
    
    # CASE 1: The product is unique to one file
    if len(categories) == 1:
        actual_cat = categories[0]
        final_output[actual_cat].append(item_data)
        
    # CASE 2: The product leaked (exists in BOTH files)
    else:
        print(f"Alert: '{name}' found in BOTH {categories}")
        # Option A: Move to a 'conflicts' key to check manually
        item_data['detected_in'] = categories
        final_output["conflicts"].append(item_data)
        
        # Option B: If you prefer to force it into Electronics 
        # (Assuming Electronics is usually the 'correct' one for leaks)
        # final_output["electronics"].append(item_data)

# Save the result
with open('checked_combined_data.json', 'w') as f:
    json.dump(final_output, f, indent=4)

print("\nScan Complete.")
print(f"Electronics Unique: {len(final_output['electronics'])}")
print(f"Beauty Unique: {len(final_output['beauty'])}")
print(f"Leaks/Duplicates found: {len(final_output['conflicts'])}")
