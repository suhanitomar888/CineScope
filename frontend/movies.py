"""Movie search and genre filtering page."""

import re

import streamlit as st

from database import db
from frontend.movie_cards import render_movie_cards


def render_movies():
    st.markdown(
        "<p class='eyebrow page-eyebrow'>YOUR CINEMA</p><h1>Discover movies</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Search by title, or browse by genre to find your next watch.")

    search_column, genre_column = st.columns([2, 1])
    with search_column:
        search = st.text_input(
            "Movie title",
            placeholder="Try Toy Story, Batman, Titanic...",
        )
    with genre_column:
        genre_values = db.movies.distinct("genres")
        genre_values = sorted(
            {
                genre.strip()
                for genre in genre_values
                if isinstance(genre, str) and genre.strip()
            },
            key=str.casefold,
        )
        selected_genre = st.selectbox("Genre", ["All Genres"] + genre_values)

    query = {}
    if search:
        query["title"] = {"$regex": re.escape(search), "$options": "i"}
    if selected_genre != "All Genres":
        query["genres"] = selected_genre

    if not search and selected_genre == "All Genres":
        st.info("Enter a title or choose a genre to see matching movies.")
        return

    movies = list(db.movies.find(query, {"_id": 0}).limit(30))
    if not movies:
        st.info("No matching movies found.")
        return

    st.markdown(f"**{len(movies)} movies found** · Showing up to 30 results")
    render_movie_cards(movies)
