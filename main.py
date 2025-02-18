import subprocess
import sys

def run_script(script):
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"Erreur lors de l'exécution de {script}")
        exit(result.returncode)

def main():
    # Exécuter le workflow de collecte d'événements
    run_script("src/gather_events.py")
        
    # Exécuter le workflow de notation des événements
    run_script("src/rate_events.py")
    # Exécuter le workflow de notation des événements
    run_script("src/viz.py")
    
if __name__ == "__main__":
    main()
