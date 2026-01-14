from flask import Flask, jsonify, request
from scraper import PortalJobScraper
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

scraper = PortalJobScraper()

@app.route('/scrape', methods=['GET'])
def run_scrape():
    # Récupérer le paramètre ?pages=X (par défaut 1)
    pages = request.args.get('pages', default=1, type=int)
    
    # 1. Lancer le scraping
    data = scraper.scrape_list(max_pages=pages)
    
    # 2. Optionnel : Sauvegarder dans un fichier local
    with open("last_results.json", "w", encoding="utf-8") as f:
        import json
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    # 3. Retourner le JSON au client
    return jsonify({
        "status": "success",
        "count": len(data),
        "data": data
    })

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Welcome to the PortalJob Scraper API",
        "endpoints": {
            "scrape": "/scrape?pages=1",
            "health": "/health"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "online", "service": "job-scraper"})

if __name__ == '__main__':
    # Mode debug pour le développement
    app.run(debug=True, port=5000)