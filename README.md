# CineScope

CineScope is a Streamlit movie discovery app backed by MongoDB Atlas. It includes movie search and genre filters, Admin-only movie management, rating and genre analytics, TMDB movie links and posters, and a K-Means clustering page.

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment.
3. Install the app dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project folder with the required MongoDB connection string. Add a TMDB API Read Access Token if poster lookup and TMDB search are wanted.
5. Configure the first Admin locally; the script asks for the username and password without displaying the password:

   ```powershell
   python scripts/configure_admin.py
   ```

6. Start CineScope:

   ```powershell
   streamlit run app.py
   ```

The `.env` file is ignored by Git. Never commit MongoDB credentials, TMDB tokens, or Admin credentials.

## Configuration

Provide these values through local `.env` settings or your deployment host's secret environment variables:

| Variable | Purpose |
| --- | --- |
| `MONGODB_URI` | MongoDB Atlas connection string for the `cinescope` database |
| `TMDB_API_KEY` | TMDB API Read Access Token; optional, but enables TMDB search and posters |
| `CINESCOPE_ADMIN_USERNAME` | Admin login username |
| `CINESCOPE_ADMIN_PASSWORD_HASH` | Salted PBKDF2-HMAC-SHA256 password hash created by `scripts/configure_admin.py` |

Deploy `app.py` as the Streamlit entry point and configure the values in the host's private environment/secrets settings. Do not upload `.env` or the local virtual environment.

## Project layout

- `app.py` — Streamlit entry point and top navigation
- `frontend/` — Home, Movies, Manage, Analytics, ML Studio, login, shared movie cards, and theme
- `database.py` — MongoDB Atlas connection and database selection
- `operations.py` — authorization-checked CRUD helpers
- `aggregations.py`, `ml_clustering.py`, `performance.py`, `validation.py` — project exercises and MongoDB/ML helpers
