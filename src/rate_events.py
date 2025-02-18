#!/usr/bin/env python3
import json
import time
import os  # ajout de os pour utiliser les variables d'environnement
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import glob
from pathlib import Path
from dotenv import load_dotenv  # import ajouté
import logging

# Configuration minimale du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_core_ranking(conference_name, driver):
    """
    Parcourt le portail CORE pour extraire les informations de classement 
    de la conférence et renvoie un dictionnaire regroupant les données.
    """
    search_url = "https://portal.core.edu.au/conf-ranks/"
    driver.get(search_url)
    
    wait = WebDriverWait(driver, 5)  # délai d'attente réduit
    result = {
        "title": "N/A",
        "acronym": "N/A",
        "source": "N/A",
        "rank": "Unranked",
        "note": "N/A",
        "dblp_link": "N/A",
        "primary_for": "N/A",
        "comments": "N/A",
        "average_rating": "N/A",
        "found": False
    }
    
    try:
        # Recherche de la conférence
        search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='search']")))
        search_box.clear()
        search_box.send_keys(conference_name)
        
        submit_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'][value='Search']")))
        submit_button.click()
        
        table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody")),
                           message="No table found")
        if "0 Results found." in table.text:
            logging.info(f"Aucun résultat pour {conference_name} (0 Results found.)")
            return result
        
        rows = table.find_elements(By.CSS_SELECTOR, "tr.evenrow, tr.oddrow")
        if not rows:
            logging.info(f"Aucun résultat pour {conference_name}")
            return result
        
        first_row = rows[0]
        result.update({
            "title": first_row.find_element(By.XPATH, "./td[1]").text.strip(),
            "acronym": first_row.find_element(By.XPATH, "./td[2]").text.strip(),
            "source": first_row.find_element(By.XPATH, "./td[3]").text.strip(),
            "rank": first_row.find_element(By.XPATH, "./td[4]").text.strip(),
            "note": first_row.find_element(By.XPATH, "./td[5]").text.strip(),
            "primary_for": first_row.find_element(By.XPATH, "./td[7]").text.strip(),
            "comments": first_row.find_element(By.XPATH, "./td[8]").text.strip(),
            "average_rating": first_row.find_element(By.XPATH, "./td[9]").text.strip(),
            "found": True
        })
        try:
            dblp_link = first_row.find_element(By.XPATH, ".//td[6]//a").get_attribute("href")
            result["dblp_link"] = dblp_link
        except Exception:
            pass
    except Exception as e:
        logging.error(f"Erreur lors de la recherche de {conference_name}: {e}")
    
    return result

def extract_conference_name(conf):
    """
    Extrait le nom de la conférence à partir du champ 'page_title'.
    Si 'page_title' n'est pas disponible, utilise 'event_name'.
    """
    title = conf.get("page_title", "")
    if title:
        parts = title.split(" ")
        return parts[0].strip() if len(parts) > 1 else title.strip()
    return conf.get("event_name", "").split(" ")[0]

def enrich_conferences(json_path, output_path):
    # Load the conference data
    with open(json_path, "r", encoding="utf-8") as f:
        conferences = json.load(f)
    
    # Charger le cache de ranking s'il existe, sinon initialiser un cache vide
    ranking_cache = load_ranking_cache() or {}
    
    # Set up Selenium with headless Chrome using webdriver-manager.
    chrome_options = Options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    for conf in conferences:
        conf_name = extract_conference_name(conf)
        if conf_name in ranking_cache:
            logging.info(f"Using cached ranking for: {conf_name}")
            conf["core_data"] = ranking_cache[conf_name]
        else:
            logging.info(f"Fetching CORE ranking for: {conf_name}")
            core_data = get_core_ranking(conf_name, driver)
            conf["core_data"] = core_data
            ranking_cache[conf_name] = core_data
            logging.info(f"Found ranking: {core_data['rank']} for {conf_name}")
            store_ranking_cache(ranking_cache)  # Stocke le cache après chaque fetch
            time.sleep(2)
    
    driver.quit()
    
    # Sauvegarder le cache mis à jour
    store_ranking_cache(ranking_cache)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(conferences, f, indent=2, ensure_ascii=False)
    
    logging.info(f"Enriched JSON written to {output_path}")

def process_all_json_files(input_dir="output_json", output_dir="data_output/enriched_json"):
    """Process all JSON files in the input directory and save enriched versions."""
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)
    
    # Get list of all JSON files in input directory
    json_files = glob.glob(f"{input_dir}/*.json")
    logging.info(f"Found {len(json_files)} JSON files to process")
    
    # Set up Chrome driver once for all files
    chrome_options = Options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        for json_file in json_files:
            logging.info(f"\nProcessing {json_file}")
            # Create output filename
            output_file = Path(output_dir) / Path(json_file).name.replace('.json', '_enriched.json')
            
            # Process the file
            with open(json_file, "r", encoding="utf-8") as f:
                conferences = json.load(f)
            
            # Enrich each conference in the file
            for conf in conferences:
                conf_name = extract_conference_name(conf)
                logging.info(f"Fetching CORE ranking for: {conf_name}")
                core_data = get_core_ranking(conf_name, driver)
                conf["core_data"] = core_data
                logging.info(f"Found ranking: {core_data['rank']} for {conf_name}")
                time.sleep(2)  # Be polite to the server
            
            # Save enriched data
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(conferences, f, indent=2, ensure_ascii=False)
            logging.info(f"Saved enriched data to {output_file}")
            
    finally:
        driver.quit()

def rate_events(events):
    """
    Exemple de notation : ajoute la clé 'rating' en fonction de la présence d'une deadline.
    """
    rated = []
    for event in events:
        event_copy = event.copy()
        event_copy['rating'] = 1 if event.get('deadline') != "N/A" else 0
        rated.append(event_copy)
    return rated

def load_ranking_cache():
    """
    Charge le cache des classements depuis un fichier JSON.
    """
    base_output_dir = os.getenv("DATA_OUTPUT", "data_output")
    cache_file = os.path.join(base_output_dir, "cache", "ranking_cache.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def store_ranking_cache(cache):
    """
    Sauvegarde le cache des classements dans un fichier JSON.
    """
    base_output_dir = os.getenv("DATA_OUTPUT", "data_output")
    cache_dir = os.path.join(base_output_dir, "cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_file = os.path.join(cache_dir, "ranking_cache.json")
    with open(cache_file, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=4)

def get_raw_results():
    # ...existing code utilisant Selenium pour récupérer les résultats bruts...
    # Simuler ici la récupération de résultats bruts
    raw_results = []  # Remplacer par la logique réelle
    return raw_results

def main():
    load_dotenv()  # Charger les variables d'environnement depuis .env
    base_output_dir = os.getenv("DATA_OUTPUT", "data_output")
    output_file = os.path.join(base_output_dir, 'output.json')
    if not os.path.exists(output_file):
        logging.error(f"Fichier de sortie {output_file} introuvable.")
        return

    logging.info(f"Enrichissement des conférences dans {output_file}")
    enrich_conferences(json_path=output_file, output_path=output_file)
    
    # Poursuite du traitement sur output.json
    with open(output_file, 'r', encoding="utf-8") as f:
        events = json.load(f)
    rated = rate_events(events)
    rated_file = os.path.join(base_output_dir, "rated_events.json")
    with open(rated_file, 'w', encoding="utf-8") as rf:
        json.dump(rated, rf, indent=4)
    logging.info(f"Les événements notés ont été sauvegardés dans {rated_file}")

if __name__ == "__main__":
    main()