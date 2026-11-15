"""Small, authorization-checked CRUD helpers for the CineScope database."""

import os
import re

from dotenv import load_dotenv
from pymongo import MongoClient

from frontend.auth import require_admin

load_dotenv()
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["cinescope"]


def add_movie(movie_id=None, title=None, genres=None):
    """Insert a movie; pass movie_id=None to allocate the next numeric ID."""
    require_admin()
    title = str(title or "").strip()
    if not title:
        raise ValueError("A movie title is required.")
    duplicate = db.movies.find_one(
        {"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}},
        {"_id": 1},
    )
    if duplicate:
        raise ValueError("A movie with that title already exists.")
    if movie_id is None:
        highest_movie = db.movies.find_one(
            {"movieId": {"$type": "number"}}, sort=[("movieId", -1)]
        )
        movie_id = int(highest_movie["movieId"]) + 1 if highest_movie else 1
    if db.movies.find_one({"movieId": movie_id}, {"_id": 1}):
        raise ValueError("That movieId already exists.")
    movie = {
        "movieId": movie_id,
        "title": title,
        "genres": genres if isinstance(genres, list) else [],
    }
    db.movies.insert_one(movie)
    return movie_id


def search_movies(title):
    """Read movies whose title contains the provided text (case-insensitive)."""
    import re

    return list(
        db.movies.find(
            {"title": {"$regex": re.escape(str(title or "")), "$options": "i"}},
            {"_id": 0},
        ).limit(50)
    )


def update_movie(movie_id, new_title):
    """Change only the movie title; metadata and related collection rows stay intact."""
    require_admin()
    new_title = str(new_title or "").strip()
    if not new_title:
        raise ValueError("A movie title is required.")
    return db.movies.update_one(
        {"movieId": int(movie_id)},
        {"$set": {"title": new_title}},
    )


def delete_movie(movie_id, confirmed=False):
    """Delete only the selected movie document after an explicit confirmation."""
    require_admin()
    if confirmed is not True:
        raise ValueError("Explicit confirmation is required before deletion.")
    return db.movies.delete_one({"movieId": int(movie_id)})
