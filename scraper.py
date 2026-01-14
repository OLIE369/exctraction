import requests
from bs4 import BeautifulSoup
import json
import time
import random
import re
import logging
from datetime import datetime

class PortalJobScraper:
    def __init__(self):
        self.base_url = "https://www.portaljob-madagascar.com/search/advanced/motcle/informatique/res/1/page/{}"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        self.skills_keywords = {
            "Languages": [r"Python", r"Java", r"JavaScript", r"PHP", r"C#"],
            "Frameworks": [r"Django", r"Flask", r"React", r"Angular", r"Node\.js", r"Symfony"],
            "DevOps": [r"Docker", r"Kubernetes", r"Git", r"AWS", r"CI/CD"]
        }

    def _get_headers(self):
        return {"User-Agent": self.user_agent}

    def _extract_skills(self, text):
        found = {}
        if not text: return found
        for cat, keywords in self.skills_keywords.items():
            matches = {k.replace("\\", "") for k in keywords if re.search(rf'\b{k}\b', text, re.I)}
            if matches: found[cat] = list(matches)
        return found

    def scrape_job_details(self, url):
        """Scrape les détails complets d'une offre."""
        try:
            time.sleep(random.uniform(1, 2))
            res = requests.get(url, headers=self._get_headers(), timeout=30)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            
            job_data = {
                "url": url,
                "scraped_at": datetime.now().isoformat()
            }

            # 1. Extraction JSON-LD (Données structurées)
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    job_data.update({
                        "title": data.get("title"),
                        "company": data.get("hiringOrganization", {}).get("name"),
                        "description": data.get("description"), # Fallback
                        "date_posted": data.get("datePosted"),
                        "date_valid_through": data.get("validThrough"),
                        "location": data.get("jobLocation", {}).get("address", {}).get("addressLocality"),
                        "contract_type": data.get("employmentType")
                    })
                except json.JSONDecodeError:
                    logging.warning(f"Erreur JSON-LD sur {url}")

            # 2. Extraction HTML Spécifique (Plus précis)
            # Secteur
            # On cherche l'image 'activite.jpg' et on prend le texte suivant
            img_activite = soup.find('img', src=re.compile(r'activite\.jpg'))
            if img_activite and img_activite.parent:
                # Le texte est souvent dans le même bloc mais après l'image/p
                # On remonte au parent div.item_detail
                container = img_activite.find_parent('div', class_='item_detail')
                if container:
                    # On nettoie le texte du container, en ignorant le alt ou autre
                    # Une méthode simple : get_text et on nettoie
                    full_text = container.get_text(strip=True)
                    # "Comptabilité" est souvent le seul texte significatif hors balises
                    job_data["sector"] = full_text.replace("Comptabilité", "").strip() or full_text # Simplification
                    # Mieux : itérer les siblings
                    if img_activite.parent.name == 'p':
                        job_data["sector"] = img_activite.parent.next_sibling.strip() if img_activite.parent.next_sibling else container.get_text(strip=True)

            # Missions
            img_mission = soup.find('img', src=re.compile(r'mission\.jpg'))
            if img_mission:
                container = img_mission.find_parent('article', class_='item_detail') or img_mission.find_parent('div', class_='item_detail')
                if container:
                    # On peut essayer de prendre tout le texte du container
                    job_data["missions"] = container.get_text('\n', strip=True)

            # Profil
            img_profil = soup.find('img', src=re.compile(r'profil\.jpg'))
            if img_profil:
                container = img_profil.find_parent('div', class_='item_detail')
                if container:
                    job_data["profile"] = container.get_text('\n', strip=True)
            
            # Référence (Extraction depuis le titre H2 ou autre)
            ref_tag = soup.find(string=re.compile(r'Réf\.:'))
            if ref_tag:
                 job_data["reference"] = ref_tag.split("Réf.:")[-1].split("-")[0].strip()

            # Extraction des compétences depuis le texte complet
            full_desc = job_data.get("description", "") + " " + job_data.get("missions", "") + " " + job_data.get("profile", "")
            job_data["skills_detected"] = self._extract_skills(full_desc)

            return job_data

        except Exception as e:
            logging.error(f"Erreur scraping détail {url}: {e}")
            return None

    def scrape_list(self, max_pages=None):
        """Récupère les données de toutes les pages disponibles ou jusqu'à max_pages."""
        all_jobs = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
                
            url = self.base_url.format(page)
            print(f"Scraping page {page}...")
            
            try:
                res = requests.get(url, headers=self._get_headers(), timeout=30)
                # Si 404 ou redirection (fin de pagination), on arrête (PortalJob redirige souvent ou renvoie page 1 si hors limite, à vérifier)
                # Mais ici on va vérifier le bouton 'Next'
                res.raise_for_status()
                
                soup = BeautifulSoup(res.text, 'html.parser')
                articles = soup.select("article.item_annonce")
                
                if not articles:
                    print("Aucune offre trouvée sur cette page. Fin.")
                    break

                for art in articles:
                    link_tag = art.select_one("h3 a")
                    if not link_tag: continue
                    
                    link_url = link_tag.get("href")
                    print(f"  -> Scraping offre: {link_url}")
                    
                    # Pause pour ne pas spammer
                    detailed_job = self.scrape_job_details(link_url)
                    if detailed_job:
                        all_jobs.append(detailed_job)
                
                # Vérification pagination via le bouton 'Suivant'
                # Selecteur supposé: .pagination .next ou verifier lien page suivante
                next_link = soup.select_one(".pagination a.next") # Hypothèse très probable sur frameworks standards
                # Etant donné qu'on itére sur l'URL page/{}, on peut juste vérifier si on a trouvé des articles.
                # Si on est redirigé sur la page 1 (cas fréquent), on boucle infini si on checke pas l'url courante vs demandée.
                if res.url != url and page > 1:
                     print("Redirection détectée (fin pagination).")
                     break

                page += 1
                
            except Exception as e:
                logging.error(f"Erreur globale page {page}: {e}")
                break
                
        return all_jobs