import os
import json
import time
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Global Configuration
COOKIES_FILE = "cookies_raw.json"
MAX_LOOPS = 5  # As requested in step 4

# URLs provided in step 1
URLS = {
    "electronics": "https://shop-id.tokopedia.com/c/phones-electronics/601739",
    "beauty": "https://shop-id.tokopedia.com/c/beauty-personal-care/601450"
}

def clean_price(text):
    """Helper to remove non-numeric chars for storage if needed"""
    return text.replace("Rp", "").replace(".", "").strip()

def setup_driver():
    options = uc.ChromeOptions()
    
    # 1. Use the "New" Headless mode (Behaves more like a real browser)
    options.add_argument("--headless=new") 
    
    # 2. Force a standard Desktop Resolution
    options.add_argument("--window-size=1366,768")
    
    # 3. Force a Real User-Agent (Remove "Headless" from the string)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
    
    # 4. Standard bypasses
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")
    
    # Initialize
    driver = uc.Chrome(options=options)
    
    # 5. EXTRA SAFETY: Verify window size was applied (Headless sometimes ignores it)
    driver.set_window_size(1366, 768)

    return driver

def inject_cookies(driver):
    """Injects cookies handling the domain split logic"""
    try:
        with open(COOKIES_FILE, "r") as file:
            data = json.load(file)
            
        all_cookies = data['cookies'] if (isinstance(data, dict) and 'cookies' in data) else data
        
        # 1. Global Session
        driver.get("https://www.tokopedia.com/404")
        for c in [x for x in all_cookies if ".tokopedia.com" in x.get('domain', '')]:
            try:
                driver.add_cookie({
                    'name': c['name'], 'value': c['value'], 'domain': c['domain'],
                    'path': c['path'], 'expiry': int(c.get('expirationDate', c.get('expires', 0)))
                })
            except: pass

        # 2. Shop Session
        driver.get("https://shop-id.tokopedia.com/404")
        for c in [x for x in all_cookies if "shop-id.tokopedia.com" in x.get('domain', '')]:
            try:
                driver.add_cookie({
                    'name': c['name'], 'value': c['value'], 'domain': c['domain'],
                    'path': c['path'], 'expiry': int(c.get('expirationDate', c.get('expires', 0)))
                })
            except: pass
            
    except Exception as e:
        print(f"Cookie injection warning: {e}")

def save_and_append_unique(category_name, new_data):
    filename = f"{category_name}_data.json"
    
    # 1. Load existing data if file exists
    if os.path.exists(filename):
        with open(filename, "r", encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    # 2. Identify existing keys (Product Names) to prevent duplicates
    existing_names = {item['name'] for item in existing_data}

    # 3. Only append items that don't exist yet
    added_count = 0
    for item in new_data:
        if item['name'] not in existing_names:
            existing_data.append(item)
            existing_names.add(item['name']) # Add to set to prevent duplicates within the same batch
            added_count += 1

    # 4. Save back to file
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4, ensure_ascii=False)
    
    print(f"[{category_name}] Added {added_count} new unique items. Total in file: {len(existing_data)}")

def scroll_to_bottom_human(driver):
    """
    Scrolls down the page in random steps with variable pauses 
    to mimic human behavior and trigger lazy-loaded elements.
    """
    print("Starting human-like scroll...")
    
    # Get total page height
    total_height = driver.execute_script("return document.body.scrollHeight")
    current_position = 0
    
    while current_position < total_height:
        # 1. Randomize scroll step (between 300px and 700px)
        step = random.randint(300, 700)
        
        # 2. Calculate new position
        current_position += step
        
        # 3. Apply scroll command
        driver.execute_script(f"window.scrollTo(0, {current_position});")
        
        # 4. Random Wait (0.3s to 1.5s) - Mimics looking at products
        time.sleep(random.uniform(0.3, 0.8))
        
        # 5. Occasional "Scroll Up" (10% chance) - Mimics checking previous item
        if random.random() < 0.1:
            scroll_up = random.randint(100, 300)
            current_position -= scroll_up
            driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(random.uniform(0.5, 1.0))

        # 6. Update height (in case new content loaded dynamically)
        new_total_height = driver.execute_script("return document.body.scrollHeight")
        
        # If the page grew (infinite scroll), update our goal
        if new_total_height > total_height:
            total_height = new_total_height
        
        # If we reached the known bottom, break
        if current_position >= total_height:
            break

    # Final pause at the bottom to ensure last elements render
    time.sleep(1)
    print("Reached the bottom.")
    
def scrape_worker(category_name, url):
    """
    This function runs in a separate thread.
    It handles the full lifecycle for ONE category:
    Open -> Loop 5 times -> (Expand View More -> Scrape) -> Save JSON
    """
    
    print(f"{category_name} Starting worker...")
    driver = setup_driver()
    inject_cookies(driver)
    
    all_collected_data = []
    driver.get(url)
    time.sleep(5) # Initial load wait
    
    try:
        # Step 4: Loop 5 times
        for loop_index in range(1, MAX_LOOPS + 1):
            print(f"[{category_name}] Iteration {loop_index}/{MAX_LOOPS} - Navigating...")

            if loop_index > 1:
                driver.refresh()
                time.sleep(5)
            
            # Step 2: Click "View More" until "No more products"
            click_count = 0
            while True:
                try:
                    # 1. Check for "No more products" text to stop
                    # specific span with 40% opacity as per your HTML
                    scroll_to_bottom_human(driver)
                    no_more = driver.find_elements(By.XPATH, "//span[contains(text(), 'No more products')]")
                    if no_more:
                        print(f"[{category_name}] Reached 'No more products'.")
                        break

                    # 2. Find the button by TEXT "View more"
                    # We use normalize-space() to ignore extra whitespace/newlines
                    view_more_xpath = "//button[normalize-space()='View more']"
                    buttons = driver.find_elements(By.XPATH, view_more_xpath)
                    
                    if buttons:
                        btn = buttons[0]
                        
                        # Scroll to button to avoid "ElementClickInterceptedException"
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        time.sleep(1) # Small pause for scroll animation
                        
                        # Click via JS is often more robust for these infinite load buttons
                        driver.execute_script("arguments[0].click();", btn)
                        
                        click_count += 1
                        
                        # Wait for content to load
                        time.sleep(3) 
                        
                        if click_count % 5 == 0:
                            print(f"[{category_name}] Expanded {click_count} times...")
                    else:
                        # If we don't see "View more", check "No more products" one last time
                        if driver.find_elements(By.XPATH, "//span[contains(text(), 'No more products')]"):
                            print(f"[{category_name}] End of list detected.")
                            break
                        
                        # If neither is found, we might be stuck or page is loading slowly
                        print(f"[{category_name}] 'View more' button disappeared. Stopping.")
                        break
                        
                except Exception as e:
                    print(f"[{category_name}] Expansion interrupt: {e}")
                    break

            # Step 3: Collect Data (Using BeautifulSoup for speed)
            print(f"[{category_name}] Parsing page content...")
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Selector: class="w-full cursor-pointer"
            product_cards = soup.select("div.w-full.cursor-pointer")
            
            iteration_products = []
            
            for card in product_cards:
                try:
                    # 1. Image
                    img_tag = card.select_one("div.relative img")
                    img_link = img_tag.get('src', '') if img_tag else "N/A"

                    # 2. Title and Link
                    # Anchor inside the card
                    link_tag = card.select_one("a[href]")
                    product_link = link_tag.get('href', '') if link_tag else "N/A"
                    if product_link and not product_link.startswith('http'):
                        product_link = "https://shop-id.tokopedia.com" + product_link
                        
                    # Title is in h3 inside the link
                    title_tag = card.select_one("h3")
                    product_name = title_tag.get_text(strip=True) if title_tag else "N/A"

                    # 3. Rating (span class P3-Semibold)
                    # Use class substring matching because of tailwind utility classes
                    rating_tag = card.select_one("span.P3-Semibold")
                    rating = rating_tag.get_text(strip=True) if rating_tag else "0"

                    # 4. Sold (span class P3-Regular containing 'sold')
                    # We look for a P3-Regular that might contain "sold" or "terjual"
                    sold = "0"
                    p3_regular_tags = card.select("span.P3-Regular")
                    for p in p3_regular_tags:
                        txt = p.get_text(strip=True).lower()
                        if "sold" in txt or "terjual" in txt:
                            sold = txt
                            break

                    # 5. Price Logic
                    price_final = "0"
                    price_original = None
                    discount = None

                    # Check for discount percentage tag (H2-Regular text-color-UITextPrimary)
                    disc_tag = card.select_one("span.H2-Regular.text-color-UITextPrimary")
                    
                    # The main price is usually in H2-Semibold
                    price_tag = card.select_one("span.H2-Semibold.text-color-UIText1")
                    
                    if price_tag:
                        price_final = price_tag.get_text(strip=True)

                    if disc_tag:
                        discount = disc_tag.get_text(strip=True)
                        # Old price is usually line-through
                        old_price_tag = card.select_one("span.line-through")
                        if old_price_tag:
                            price_original = old_price_tag.get_text(strip=True)

                    item_data = {
                        #"loop_iteration": loop_index,
                        "name": product_name,
                        "url": product_link,
                        "image": img_link,
                        "rating": rating,
                        "sold_quantity": sold,
                        "price_current": price_final,
                        "price_original": price_original,
                        "discount": discount
                    }
                    
                    iteration_products.append(item_data)
                    
                except Exception as parse_err:
                    continue # Skip bad card
            
            # After finishing a loop or at the end of the worker:
            save_and_append_unique(category_name, iteration_products)
            
            # Refresh happen automatically at start of next loop via driver.get()
            
    except Exception as e:
        print(f"[{category_name}] Critical Error: {e}")
        driver.save_screenshot("error_debug.png")
        
    finally:
        driver.save_screenshot("final_screen.png")
        fresh_cookies = driver.get_cookies()
        print(f"Captured {len(fresh_cookies)} fresh cookies.")

        #6. Save to File
        with open("cookies_raw.json", "w") as f:
            json.dump(fresh_cookies, f, indent=4)
            
        driver.quit()
        
    return f"Finished {category_name}"

def main():
    # The loop to call the function
    for category, link in URLS.items():
    	print(f"Starting scrape for: {category}")
    	scrape_worker(category, link)

if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"Total execution time: {time.time() - start_time:.2f} seconds")
