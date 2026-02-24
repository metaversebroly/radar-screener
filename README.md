# RADAR — StockX Price Screener

Screener de prix StockX pour détecter les "trous d'air" (chutes de prix anormales) sur des jouets/collectibles (Labubu, etc.).

**Live demo :** [radar-screenerx.vercel.app](https://radar-screenerx.vercel.app)

## Fonctionnalités

- 📦 Watchlist de produits StockX (Labubu, sneakers, etc.)
- 📉 Détection des chutes de prix (trou d'air) par rapport à la médiane 30j
- 🔔 Alertes Telegram en temps réel
- ⚙️ Seuil de discount personnalisable par produit (1–99 %)
- 📱 Interface responsive (mobile, tablette, desktop)

## Stack

- **Frontend** : HTML/CSS/JS vanilla → Vercel
- **Backend** : Python FastAPI → Railway
- **Base de données** : Supabase (PostgreSQL)
- **Scraping** : Retailed.io API
- **Alertes** : Telegram bot
- **Scheduler** : APScheduler, scan toutes les 6 heures

---

## Instructions de déploiement

### 1. Supabase

Créer un projet sur [Supabase](https://supabase.com), puis exécuter ce SQL dans l'éditeur SQL :

```sql
CREATE TABLE products (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  slug text UNIQUE NOT NULL,
  name text NOT NULL,
  dip_threshold numeric DEFAULT 15,
  created_at timestamp DEFAULT now()
);

CREATE TABLE price_history (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  product_id uuid REFERENCES products(id) ON DELETE CASCADE,
  price numeric NOT NULL,
  scanned_at timestamp DEFAULT now()
);

CREATE TABLE alerts (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  product_id uuid REFERENCES products(id) ON DELETE CASCADE,
  product_name text,
  slug text,
  alert_price numeric,
  median_price numeric,
  discount_pct numeric,
  triggered_at timestamp DEFAULT now()
);
```

**Si la table `products` existe déjà**, ajouter la colonne seuil :
```sql
ALTER TABLE products ADD COLUMN IF NOT EXISTS dip_threshold numeric DEFAULT 15;
```

Récupérer `SUPABASE_URL` et `SUPABASE_KEY` (service_role) dans Settings → API.

### 2. Telegram

1. Créer un bot via [@BotFather](https://t.me/BotFather) et récupérer le token
2. Trouver le CHAT_ID : envoyer `/start` à ton bot (@RadarStockX_bot)
3. Ouvrir dans le navigateur : `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Copier le `chat.id` dans la réponse JSON

### 3. Railway

1. Connecter le repo GitHub à [Railway](https://railway.app)
2. Créer un nouveau service et sélectionner le repo
3. **Root Directory** : `backend` (important pour monorepo)
4. **Start command** : `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Port** : 8000 (dans Settings → Networking si demandé)
6. Ajouter les variables d'environnement :
   - `RETAILED_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `DIP_THRESHOLD` (optionnel, défaut 15)
   - `PORT` (géré par Railway)
7. Générer un domaine dans Settings → Networking
8. Copier l’URL générée (ex: `https://radar-screener-production.up.railway.app`)

### 4. Vercel

1. Connecter le repo GitHub à [Vercel](https://vercel.com)
2. Configurer le projet :
   - **Root Directory** : `.` (racine du repo)
   - Le `vercel.json` redirige toutes les routes vers `/frontend/index.html`
3. Dans `frontend/index.html`, remplacer `API_URL` par ton URL Railway :
   ```js
   const API_URL = 'https://ton-url.up.railway.app';
   ```
4. Déployer (chaque push déclenche un redéploiement auto)

### 5. Test final

1. Ouvrir le site Vercel
2. Ajouter un produit Labubu (ex: `https://stockx.com/fr/labubu-the-monsters-zimomo`)
3. Cliquer sur **SCAN MAINTENANT**
4. Vérifier que le message arrive sur Telegram en cas de trou d’air détecté

---

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `RETAILED_API_KEY` | Clé API Retailed.io |
| `SUPABASE_URL` | URL du projet Supabase |
| `SUPABASE_KEY` | Clé service_role Supabase |
| `TELEGRAM_BOT_TOKEN` | Token du bot Telegram |
| `TELEGRAM_CHAT_ID` | ID du chat pour les alertes |
| `DIP_THRESHOLD` | Seuil de discount pour alerte (défaut: 15) |
| `PORT` | Port du serveur (défaut: 8000) |

---

## Développement local

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec tes clés
uvicorn main:app --reload --port 8000
```

Frontend : ouvrir `frontend/index.html` et modifier `API_URL` vers `http://localhost:8000`.
