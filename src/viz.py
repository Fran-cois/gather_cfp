import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns      # Pour le style des graphiques
import geopandas as gpd
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import matplotlib.patches as mpatches  # Ajout de l'import pour les légendes
import logging
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
import gather_events
import rate_events as rate_events

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def make_cfp_unique(df):
    """
    Supprime les doublons dans le DataFrame basé sur le nom de l'événement et la date de soumission.
    """
    df_unique = df.drop_duplicates(subset=["event_name", "submission_deadline"])
    return df_unique

def prepare_data(filename="data_output/rated_events.json"):
    """
    Charge le fichier JSON et prépare les données sous forme de DataFrame ainsi que
    les informations nécessaires pour générer un diagramme de Gantt.
    """
    sns.set_style("whitegrid")
    sns.set_palette("pastel")
    filename = "data_output/output.json"
    filename = "data_output/rated_events.json"

    # Chargement des données
    try:
        with open(filename, "r", encoding="utf-8") as file:
            conferences = json.load(file)
    except FileNotFoundError as e:
        logging.error(f"Could not open file '{filename}': {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], {}, [], []
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in file '{filename}': {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], {}, [], []

    # Transformation en DataFrame et adaptation des clés
    df = pd.DataFrame(conferences)
    df = df.rename(columns={"where": "location", "deadline": "submission_deadline"})
    df["submission_deadline"] = pd.to_datetime(df["submission_deadline"], errors="coerce")
    # Suppression des lignes sans date de soumission
    df = df[df["submission_deadline"].notna()]
    # Gestion de l'absence de core_data
    df["rank"] = df.apply(
        lambda row: row["core_data"]["rank"] if "core_data" in row and isinstance(row["core_data"], dict) and "rank" in row["core_data"] else "Unknown",
        axis=1
    )

    if df.empty:
        logging.warning("DataFrame is empty after loading data.")

    # Rendre les CFP uniques
    df = make_cfp_unique(df)

    # Mapping des couleurs par rang
    rank_colors = {
        "Unknown": "dodgerblue",
        "A*": "darkred",
        "A": "crimson",
        "B": "gold",
        "C": "lightgreen"
    }

    # Création du diagramme de Gantt de base
    df_sorted = df.sort_values("submission_deadline")
    df_sorted['start_date'] = df_sorted['submission_deadline']
    df_sorted['end_date'] = df_sorted['start_date'] + pd.Timedelta(days=1)
    mask = df_sorted['start_date'].notna() & df_sorted['end_date'].notna()
    gantt_df = df_sorted[mask].reset_index(drop=True)
    y_pos = range(len(gantt_df))
    durations = [(end - start).days for start, end in zip(gantt_df['start_date'], gantt_df['end_date'])]
    gantt_colors = gantt_df["rank"].apply(lambda r: rank_colors.get(r, "dodgerblue")).tolist()

    return df, df_sorted, gantt_df, durations, rank_colors, y_pos, gantt_colors

# Script prêt à être publié (distribution externe)

def create_all_charts():
    """
    Crée et affiche tous les graphiques pour les conférences du jeu de données.
    Utilise les valeurs d'environnement 'INPUT_FILE' et 'DATA_OUTPUT'
    pour charger le fichier d'entrée et définir le répertoire de sortie.
    """
    input_filename = os.getenv("INPUT_FILE", "rated_events.json")
    base_output_dir = os.getenv("DATA_OUTPUT", "data_output")
    output_dir = os.path.join(base_output_dir, "graphs")
    # Charger les données depuis le fichier défini par l’ENV
    df, df_sorted, gantt_df, durations, rank_colors, y_pos, gantt_colors = prepare_data(input_filename)
    logging.info("Starting chart creation process.")
    if df is None or df.empty:
        logging.warning("No data available for chart creation.")
        return
    # Création du premier graphique Gantt
    plt.figure(figsize=(12, 6))
    plt.barh(list(y_pos), durations, left=gantt_df['start_date'], color=gantt_colors)
    plt.yticks(list(y_pos), gantt_df["event_name"])
    plt.xlabel("Date")
    plt.title("Gantt Chart of Conference Event Duration")
    plt.grid(axis="x", linestyle="--", alpha=0.7)
    # Ajout de la légende pour les couleurs associées aux rangs
    legend_handles = [mpatches.Patch(color=rank_colors[key], label=key) for key in rank_colors]
    plt.legend(handles=legend_handles, title="Rank")
    plt.gca().xaxis_date()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%y"))
    for idx, row in gantt_df.iterrows():
        duration = (row['end_date'] - row['start_date']).days
        mid_time = row['start_date'] + pd.Timedelta(days=duration/2)
        min_pages = row.get("minimum_pages", "N/A")
        plt.text(mid_time, idx, str(min_pages), color="black", va="center", ha="center", fontsize=8)
        # Annotation si "workshop" dans les catégories
        if any("workshop" in cat.lower() for cat in row.get("categories", [])):
            plt.text(mid_time, idx, "Workshop", color="blue", va="bottom", ha="center", fontsize=8)
    plt.tight_layout()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    try:
        plt.savefig(os.path.join(output_dir, "wholeCfp.png"))
        logging.info(f"File saved: {os.path.join(output_dir, 'wholeCfp.png')}")
    except Exception as e:
        logging.error(f"Error while saving chart: {e}")
    plt.close()

    # Nouveau graphique : filtré par "database" et "data mining"
    filter_keywords = ["database", "data mining", "pattern recognition", "big data", "computer science"]
    db_gantt = gantt_df[gantt_df["categories"].apply(
        lambda x: any(any(keyword in str(cat).lower() for keyword in filter_keywords)
                    for cat in (x if isinstance(x, list) else str(x).split(',')))
    )]
    y_pos_db = range(len(db_gantt))
    durations_db = [(end - start).days for start, end in zip(db_gantt['start_date'], db_gantt['end_date'])]
    database_colors = db_gantt["rank"].apply(lambda r: rank_colors.get(r, "dodgerblue")).tolist()

    plt.figure(figsize=(12, 6))
    plt.barh(list(y_pos_db), durations_db, left=db_gantt['start_date'], color=database_colors)
    plt.yticks(list(y_pos_db), db_gantt["event_name"])
    plt.xlabel("Date")
    plt.title("Gantt Chart of Conference Event Duration (Database)")
    plt.grid(axis="x", linestyle="--", alpha=0.7)
    # Ajout de la légende pour les couleurs associées aux rangs (Database)
    legend_handles = [mpatches.Patch(color=rank_colors[key], label=key) for key in rank_colors]
    plt.legend(handles=legend_handles, title="Rank")
    plt.gca().xaxis_date()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%y"))

    def annotate_bar(idx, row):
        """Ajoute une annotation combinant 'minimum_pages' et 'rank' à la barre."""
        duration = (row['end_date'] - row['start_date']).days
        mid_time = row['start_date'] + pd.Timedelta(days=duration / 2)
        min_pages = row.get("minimum_pages", "N/A")
        conf_rank = row.get("rank", "Unknown")
        plt.text(mid_time, idx, f"{min_pages}, {conf_rank}", color="black", va="center", ha="center", fontsize=8)

    for idx, row in db_gantt.iterrows():
        annotate_bar(idx, row)
        # Annotation si "workshop" dans les catégories
        if any("workshop" in cat.lower() for cat in row.get("categories", [])):
            duration = (row['end_date'] - row['start_date']).days
            mid_time = row['start_date'] + pd.Timedelta(days=duration / 2)
            plt.text(mid_time, idx, "Workshop", color="blue", va="bottom", ha="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "filtered_by_categories.png"))
    plt.close()

    # Graphique en barres pour la répartition des rangs
    plt.figure(figsize=(10, 6))
    ranking_counts = df["rank"].value_counts().sort_values()
    bar_colors = [rank_colors.get(rank, "dodgerblue") for rank in ranking_counts.index]
    ranking_counts.plot(kind="barh", color=bar_colors)
    plt.xlabel("Count")
    plt.ylabel("Rank")
    plt.title("Conference Rankings Distribution")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "rank_distribution.png"))
    plt.close()

    # Carte des emplacements des conférences
    def simulate_geocode(loc):
        try:
            lat, lon = map(float, loc.split(","))
            return lat, lon
        except:
            return None

    coords = df["location"].dropna().apply(simulate_geocode).dropna()
    if not coords.empty:
        lats, lons = zip(*coords)
        world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
        fig, ax = plt.subplots(figsize=(12, 8))
        world.plot(ax=ax, color="lightgray", edgecolor="white")
        ax.scatter(lons, lats, color="red", s=50, zorder=5)
        plt.title("Conference Locations")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "conference_locations.png"))
        plt.close()
    else:
        print("No valid location data for mapping.")

    # Création des graphiques mensuels
    plot_monthly_gantt(df_sorted, rank_colors)

# Commenter ou supprimer l'importation de ace_tools
# import ace_tools as tools
# tools.display_dataframe_to_user(name="Conference Data", dataframe=df)

def filter_events_by_category(events, target_categories):
    """
    Filtre la liste d'événements en fonction des catégories souhaitées.

    Args:
        events (list): Liste des événements (dictionnaires).
        target_categories (list): Liste de catégories cibles à filtrer.

    Returns:
        list: La liste des événements filtrés.
    """
    filtered = []
    for event in events:
        # Comparer les catégories en minuscules
        cats = [cat.lower() for cat in event.get("categories", [])]
        if any(tc in cats for tc in target_categories):
            filtered.append(event)
    return filtered

# Nouvelle fonction pour générer un graphique de Gantt par mois
def plot_monthly_gantt(df, rank_colors):
    """
    Génère des graphiques de Gantt mensuels pour les événements ayant des dates valides.

    Args:
        df (pd.DataFrame): DataFrame contenant les informations des événements.
        rank_colors (dict): Dictionnaire de mappage entre rang et couleur.
    """
    import os  # s'assurer que os est importé
    base_output_dir = os.getenv("DATA_OUTPUT", "data_output")
    graphs_dir = os.path.join(base_output_dir, "graphs/by_months")
    if not os.path.exists(graphs_dir):
        os.makedirs(graphs_dir)
    # Filtrer les événements ayant start_date, end_date et submission_deadline valides
    mask = df['start_date'].notna() & df['end_date'].notna() & df['submission_deadline'].notna()
    valid_df = df[mask]
    # Filtrer pour n'inclure que les mois février (2), mars (3) et avril (4)
    #valid_df = valid_df[valid_df["submission_deadline"].dt.month.isin([2, 3, 4])]
    # Groupement par mois basé sur submission_deadline
    grouped = valid_df.groupby(valid_df["submission_deadline"].dt.to_period("M"))
    for period, group in grouped:
        print(f"[DEBUG] Processing period: {period} with {len(group)} events")  # debug statement ajouté
        y_pos_month = range(len(group))
        durations_month = [(end - start).days for start, end in zip(group['start_date'], group['end_date'])]
        monthly_colors = group["rank"].apply(lambda r: rank_colors.get(r, "dodgerblue")).tolist()
        plt.figure(figsize=(12, 6))
        plt.barh(list(y_pos_month), durations_month, left=group['start_date'], color=monthly_colors)
        plt.yticks(list(y_pos_month), group["event_name"])
        plt.xlabel("Date")
        plt.title(f"Gantt Chart for {period} (Monthly)")
        plt.grid(axis="x", linestyle="--", alpha=0.7)
        legend_handles = [mpatches.Patch(color=rank_colors[key], label=key) for key in rank_colors]
        plt.legend(handles=legend_handles, title="Rank")
        plt.gca().xaxis_date()
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%y"))
        # Annotation (même logique que “db_gantt”)
        for idx, row in group.iterrows():
            duration = (row['end_date'] - row['start_date']).days
            mid_time = row['start_date'] + pd.Timedelta(days=duration / 2)
            min_pages = row.get("minimum_pages", "N/A")
            conf_rank = row.get("rank", "Unknown")
            plt.text(mid_time, idx, f"{min_pages}, {conf_rank}", color="black", va="center", ha="center", fontsize=8)
            if any("workshop" in cat.lower() for cat in row.get("categories", [])):
                plt.text(mid_time, idx, "Workshop", color="blue", va="bottom", ha="center", fontsize=8)
        plt.tight_layout()
        file_path = os.path.join(graphs_dir, f"gantt_{period}.png")
        plt.savefig(file_path)
        plt.close()

def main():
    """
    Point d'entrée principal du script.
    - Charge les données depuis un fichier JSON.
    - Filtre les événements en fonction de certaines catégories.
    - Appelle la fonction de création de graphiques.
    - Sauvegarde le DataFrame final en CSV et JSON.
    """
    # Charger les données depuis output.json
    with open("output.json", "r") as f:
        events = json.load(f)
    
    target_categories = ["database", "data mining"]
    filtered_events = filter_events_by_category(events, target_categories)
    
    # Affichage uniquement des événements filtrés
    print("Événements filtrés :")
    for event in filtered_events:
        print(f"- {event.get('event_name', 'Inconnu')} | Catégories : {event.get('categories')}")
    
    # Commenter ou supprimer la partie relative aux graphiques mensuels
    # print("\nAffichage d'un graphique par mois :")
    create_all_charts()
    
    # Charger les données curatées depuis output.json
    with open("output.json", "r", encoding="utf-8") as file:
        data = json.load(file)
    df = pd.DataFrame(data)
    # ...eventuelles transformations sur df...
    base_output_dir = os.getenv("DATA_OUTPUT", "data_output")
    df.to_csv(os.path.join(base_output_dir, "curated_df.csv"), index=False)
    print(f"Le DataFrame curaté a été sauvegardé dans '{os.path.join(base_output_dir, 'curated_df.csv')}'")
    
    # Nouvelle sortie en JSON
    df.to_json(os.path.join(base_output_dir, "curated_df.json"), orient="records", indent=4)
    print(f"Le DataFrame curaté a été sauvegardé dans '{os.path.join(base_output_dir, 'curated_df.json')}'")

if __name__ == "__main__":
    main()
