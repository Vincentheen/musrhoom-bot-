from flask import Flask
from threading import Thread

# Création de l'application Flask
app = Flask(__name__)


@app.route('/')
def home():
    return "I'm alive"


# Fonction pour démarrer le serveur Flask
def run():
    app.run(host='0.0.0.0', port=8080)


# Fonction pour garder le serveur Flask actif dans un thread séparé
def keep_alive():
    t = Thread(target=run)
    t.start()
