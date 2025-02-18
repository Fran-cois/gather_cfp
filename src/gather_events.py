import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from datetime import datetime  # import ajouté
from bs4 import BeautifulSoup  # import ajouté pour améliorer le parsing HTML

def setup_driver(headless=False):
    """Initialize and return a Chrome WebDriver instance."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def format_deadline(deadline_str):
    """Format deadline string to standard format."""
    if deadline_str == "N/A":
        return deadline_str
    # Remove any trailing timezone or extra info
    deadline_str = deadline_str.split('(')[0].strip()
    try:
        # Parse the date string and format as dd/mm/yy
        date_obj = datetime.strptime(deadline_str, '%b %d, %Y')
        return date_obj.strftime('%d/%m/%y')
    except ValueError:
        return deadline_str

def process_data_table(driver):
    """
    Locate the data table by its header and extract event data.
    Each event spans two rows:
      - Row 1: Contains the event name (with a link) and description.
      - Row 2: Contains "When", "Where", and "Deadline" details.
      
    Returns:
        A list of dictionaries containing extracted event data.
    """
    events = []
    try:
        # Wait until the table with header "Event" is available.
        table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//table[tbody/tr[1]/td[contains(., 'Event')]]")
            )
        )
    except Exception as e:
        print("Error locating the data table:", e)
        return events

    # Fetch all rows in the table
    rows = table.find_elements(By.XPATH, ".//tr")
    if len(rows) < 3:
        print("Not enough rows found in the table.")
        return events

    # The first row is the header. The remaining rows contain events in pairs.
    num_events = (len(rows) - 1) // 2
    print("Found", num_events, "event(s) on this page.")
    for i in range(1, len(rows), 2):
        try:
            # First row for the event record
            row1 = rows[i]
            cells1 = row1.find_elements(By.TAG_NAME, "td")
            if len(cells1) < 2:
                print("Insufficient cells in the first row of the record.")
                continue

            # Extract event name and link from the first cell
            try:
                link_elem = cells1[0].find_element(By.TAG_NAME, "a")
                event_name = link_elem.text.strip()
                event_link = link_elem.get_attribute("href")
            except Exception as e:
                print("Error extracting event link:", e)
                event_name = cells1[0].text.strip()
                event_link = "N/A"

            # Extract description from the second cell.
            description = cells1[1].text.strip() if len(cells1) >= 2 else "N/A"

            # Second row contains When, Where, and Deadline details.
            when = where = deadline = "N/A"
            if i + 1 < len(rows):
                row2 = rows[i + 1]
                cells2 = row2.find_elements(By.TAG_NAME, "td")
                if len(cells2) >= 3:
                    when = cells2[0].text.strip()
                    where = cells2[1].text.strip()
                    deadline = format_deadline(cells2[2].text.strip())

            event_data = {
                "event_name": event_name,
                "description": description,
                "link": event_link,
                "when": when,
                "where": where,
                "deadline": deadline
            }
            events.append(event_data)
        except Exception as e:
            print("Error processing an event record:", e)
            continue
    return events

def click_next_page(driver):
    """
    Check for a clickable "next" link in the pagination area and click it.
    Returns True if the next page is loaded, or False if not found.
    """
    try:
        # Look for an anchor tag with text "next".
        next_link = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "next"))
        )
        next_link.click()
        # Wait for the page to refresh by waiting until the next_link becomes stale.
        WebDriverWait(driver, 10).until(EC.staleness_of(next_link))
        return True
    except Exception as e:
        print("No next link found or error clicking next:", e)
        return False

def scrape_event_details(driver, event_url):
    """
    Navigate to the event URL and extract additional details using BeautifulSoup.
    
    Returns:
        A dictionary containing additional details from the event page.
    """
    import re  # import pour les expressions régulières
    details = {}
    try:
        driver.get(event_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        html = driver.page_source
        #details["page_content"] = html
        
        # Utiliser BeautifulSoup pour parser le contenu HTML
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        details["page_title"] = title_tag.text.strip() if title_tag else driver.title
        meta_desc = soup.find("meta", attrs={"name": "description"})
        details["meta_description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else "N/A"

        # Extraction du deadline détaillé
        deadline_match = re.search(r"Deadline\s*:\s*([\w\s,\-]+)", html, re.IGNORECASE)
        details["detailed_deadline"] = deadline_match.group(1).strip() if deadline_match else "N/A"

        # Extraction du review time
        review_match = re.search(r"Review Time\s*:\s*([\w\s,\-]+)", html, re.IGNORECASE)
        details["review_time"] = review_match.group(1).strip() if review_match else "N/A"

        # Extraction du conference rank
        rank_match = re.search(r"Conference Rank\s*:\s*([\w\s,\-]+)", html, re.IGNORECASE)
        details["conference_rank"] = rank_match.group(1).strip() if rank_match else "N/A"

        # Détection si l'événement est un workshop (recherche du mot "workshop")
        details["is_workshop"] = True if soup.find(text=re.compile("workshop", re.IGNORECASE)) else False

        # Extraction du nombre minimum de pages
        pages_match = re.search(r"Minimum Pages\s*:\s*(\d+)", html, re.IGNORECASE)
        details["minimum_pages"] = int(pages_match.group(1)) if pages_match else "N/A"

        # Nouvelle extraction : lien du site web de l'événement
        link_text = soup.find(text=lambda x: x and "Link:" in x)
        if link_text:
            parent_td = link_text.find_parent("td")
            if parent_td:
                website_a = parent_td.find("a", href=True)
                details["website_link"] = website_a["href"] if website_a else "N/A"
            else:
                details["website_link"] = "N/A"
        else:
            details["website_link"] = "N/A"

        # Nouvelle extraction : catégories de l'événement
        cat_h5 = soup.find("h5")
        if cat_h5 and "Categories" in cat_h5.get_text():
            a_tags = cat_h5.find_all("a")
            # Exclure le lien de l'étiquette "Categories"
            details["categories"] = [a.get_text(strip=True) for a in a_tags if "Categories" not in a.get_text()]
        else:
            details["categories"] = []

    except Exception as e:
        details["error"] = str(e)
    return details

# Charger les variables d'environnement depuis .env
load_dotenv()

def main():
    # URL for the first page (adjust as needed)
    url = "http://www.wikicfp.com/cfp/call?conference=artificial%20intelligence"
    url="http://www.wikicfp.com/cfp/call?conference=computer%20science&skip=1"
    driver = setup_driver(headless=False)
    all_events = []
    
    # Charger la variable MAX_PAGES depuis .env (par défaut 5 pages)
    max_pages = int(os.environ.get("MAX_PAGES", 50))
    page_count = 0
    
    try:
        driver.get(url)
        # Process each page until no "next" link is found or max pages reached.
        while True:
            page_count += 1
            print(f"\nProcessing page {page_count}...")
            events = process_data_table(driver)
            all_events.extend(events)
            if page_count >= max_pages or not click_next_page(driver):
                if page_count >= max_pages:
                    print("Maximum page limit reached.")
                else:
                    print("No further pages found. Exiting pagination loop.")
                break

        # Now that we've collected all event data from the table,
        # perform additional scraping on each event's detail page.
        print("\nStarting additional scraping on extracted event URLs...")
        all_events_details = []
        for event in all_events:
            if event["link"] and event["link"] != "N/A":
                details = scrape_event_details(driver, event["link"])
                new_details = {**event, **details}
                all_events_details.append(new_details)

        # Output the complete data in JSON format.
        json_output = json.dumps(all_events_details, indent=4)
        # Récupérer le chemin du fichier de sortie depuis .env
        output_file = os.environ.get('OUTPUT_FILE', 'output.json')
        with open(output_file, 'w') as f:
            f.write(json_output)
        print(f"\nDonnées sauvegardées dans {output_file}")

        # Sauvegarder les données en cache pour rate_events
        base_output_dir = os.getenv("DATA_OUTPUT", "data_output")
        cache_dir = os.path.join(base_output_dir, "cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        cache_file = os.path.join(cache_dir, "cache_output.json")
        with open(cache_file, 'w') as cf:
            cf.write(json_output)
        print(f"Données mises en cache dans {cache_file}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()