"""Homepage with a rotating featured-movie banner and popular movie cards."""

import re
import time
from html import escape

import streamlit as st

from database import db
from frontend.movie_cards import (
    _poster_image,
    genre_names,
    get_rating_summaries,
    render_movie_cards,
)

HOME_MOVIE_BATCH_SIZE = 12


def _popular_movies(limit=7, minimum_rating_count=20):
    """Return popular movies with enough ratings to make their averages useful."""
    pipeline = [
        {
            "$group": {
                "_id": "$movieId",
                "averageRating": {"$avg": "$rating"},
                "ratingCount": {"$sum": 1},
            }
        },
        {"$match": {"ratingCount": {"$gte": minimum_rating_count}}},
        {"$sort": {"ratingCount": -1, "averageRating": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "movies",
                "localField": "_id",
                "foreignField": "movieId",
                "as": "movie",
            }
        },
        {"$unwind": "$movie"},
        {
            "$project": {
                "_id": 0,
                "movieId": "$_id",
                "title": "$movie.title",
                "genres": "$movie.genres",
                "tmdbId": "$movie.tmdbId",
                "imdbId": "$movie.imdbId",
                "averageRating": 1,
                "ratingCount": 1,
            }
        },
    ]
    return list(db.ratings.aggregate(pipeline))


def _add_sample_movies(movies, needed):
    """Fill a short featured list from real movie records in MongoDB."""
    if needed <= 0:
        return movies

    existing_ids = [movie.get("movieId") for movie in movies]
    samples = list(
        db.movies.aggregate(
            [
                {"$match": {"movieId": {"$nin": existing_ids}}},
                {"$sample": {"size": needed}},
                {
                    "$project": {
                        "_id": 0,
                        "movieId": 1,
                        "title": 1,
                        "genres": 1,
                        "tmdbId": 1,
                        "imdbId": 1,
                    }
                },
            ]
        )
    )
    summaries = get_rating_summaries(
        [movie.get("movieId") for movie in samples if movie.get("movieId") is not None]
    )
    for movie in samples:
        summary = summaries.get(movie.get("movieId"), {})
        movies.append(
            {
                **movie,
                "averageRating": summary.get("average"),
                "ratingCount": summary.get("count", 0),
            }
        )
    return movies


def _select_hero_slide(index):
    """Select a slide and restart its six-second rotation interval."""
    st.session_state["home_hero_index"] = index
    st.session_state["home_hero_last_rotation"] = time.monotonic()


def _advance_hero_index(state, slide_count, now):
    """Advance the stored slide index once for each elapsed six-second interval."""
    if slide_count < 1:
        return 0
    if "home_hero_index" not in state:
        state["home_hero_index"] = 0
        state["home_hero_last_rotation"] = now
    else:
        last_rotation = state.get("home_hero_last_rotation", now)
        elapsed = now - last_rotation
        if elapsed >= 6:
            rotations = max(1, int(elapsed // 6))
            state["home_hero_index"] = (state["home_hero_index"] + rotations) % slide_count
            state["home_hero_last_rotation"] = last_rotation + rotations * 6
    state["home_hero_index"] %= slide_count
    return state["home_hero_index"]


def _title_and_year(value):
    """Split a MovieLens title such as 'Toy Story (1995)' into title and year."""
    title = str(value or "Untitled")
    match = re.search(r"\s*\((\d{4})\)\s*$", title)
    if not match:
        return title, "Year unavailable"
    return title[: match.start()].strip(), match.group(1)


def _load_next_home_movie_batch():
    """Append the next twelve real movie documents to this user's Home list."""
    offset = st.session_state.get("home_movie_offset", 0)
    batch = list(
        db.movies.find({}, {"_id": 0})
        .sort("movieId", 1)
        .skip(offset)
        .limit(HOME_MOVIE_BATCH_SIZE + 1)
    )
    movies_to_add = batch[:HOME_MOVIE_BATCH_SIZE]
    already_loaded = {
        movie.get("movieId") for movie in st.session_state.get("home_movies", [])
    }
    new_movies = []
    for movie in movies_to_add:
        movie_id = movie.get("movieId")
        if movie_id in already_loaded:
            continue
        already_loaded.add(movie_id)
        new_movies.append(movie)

    st.session_state["home_movies"] = st.session_state.get("home_movies", []) + new_movies
    st.session_state["home_movie_offset"] = offset + len(movies_to_add)
    st.session_state["home_movies_have_more"] = len(batch) > HOME_MOVIE_BATCH_SIZE


@st.fragment(run_every=6)
def _render_featured_carousel(movies):
    """Render and automatically rotate the Home hero without rerunning the page."""
    if not movies:
        st.markdown(
            '<section class="hero home-hero"><div class="hero-content">'
            '<p class="eyebrow">CINESCOPE</p><h1>Your next great story awaits.</h1>'
            '<p class="hero-copy">Add movies to your collection to start exploring.</p>'
            '</div></section>',
            unsafe_allow_html=True,
        )
        return

    slide_count = len(movies)
    active_index = _advance_hero_index(st.session_state, slide_count, time.monotonic())
    featured = movies[active_index]
    title, year = _title_and_year(featured.get("title"))
    genres = ", ".join(genre_names(featured.get("genres"))) or "Genre not listed"
    average = featured.get("averageRating")
    rating_text = f"{average:.2f} / 5" if average is not None else "Not rated / 5"
    rating_count = int(featured.get("ratingCount") or 0)
    poster_url = _poster_image(featured.get("tmdbId"))

    background_style = ""
    if poster_url and poster_url.startswith("https://image.tmdb.org/t/p/"):
        background_style = (
            "background-image: linear-gradient(90deg, rgba(16,15,14,.97) 0%, "
            "rgba(21,21,21,.82) 52%, rgba(21,21,21,.48) 100%), "
            f"url('{escape(poster_url, quote=True)}');"
        )

    st.markdown(
        f"""
        <section class="hero home-hero" style="{background_style}">
            <div class="hero-content">
                <p class="eyebrow">CINESCOPE FEATURE · {active_index + 1} / {slide_count}</p>
                <h1>{escape(title)}</h1>
                <p class="hero-copy">A CineScope community favorite, selected from your movie collection.</p>
                <p class="hero-meta">{escape(year)} &nbsp; | &nbsp; {escape(genres)} &nbsp; | &nbsp;
                    {escape(rating_text)} from {rating_count:,} ratings</p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="home_hero_dots"):
        dot_slots = st.columns([1, 1, *([0.25] * slide_count), 1, 1])
        dot_columns = dot_slots[2:-2]
        for index, column in enumerate(dot_columns):
            with column:
                st.button(
                    "●",
                    key=f"home_hero_dot_{index}",
                    help=f"Show featured movie {index + 1}",
                    type="primary" if index == active_index else "secondary",
                    on_click=_select_hero_slide,
                    args=(index,),
                )


def render_home():
    movie_count = db.movies.count_documents({})
    rating_count = db.ratings.count_documents({})
    tag_count = db.tags.count_documents({})
    popular = _popular_movies()

    # Relax the minimum only when fewer than five movies meet it.
    if len(popular) < 5:
        popular = _popular_movies(minimum_rating_count=1)
    popular = _add_sample_movies(popular, max(0, 5 - len(popular)))
    featured_movies = popular[:5]

    _render_featured_carousel(featured_movies)

    if st.button("Explore Movies", key="home_explore_movies", type="primary"):
        st.session_state["cinescope_page"] = "Movies"
        st.rerun()

    st.markdown(
        "<div class='collection-strip'>"
        f"<span><strong>{movie_count:,}</strong> MOVIES</span>"
        f"<span><strong>{rating_count:,}</strong> RATINGS</span>"
        f"<span><strong>{tag_count:,}</strong> TAGS</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if "home_movies" not in st.session_state:
        st.session_state["home_movies"] = []
        st.session_state["home_movie_offset"] = 0
        st.session_state["home_movies_have_more"] = True
        _load_next_home_movie_batch()

    st.markdown("## Explore the collection")
    st.caption(
        f"Showing {len(st.session_state['home_movies']):,} of {movie_count:,} movies. "
        "CineScope ratings are calculated from the existing MovieLens ratings."
    )
    if st.session_state["home_movies"]:
        render_movie_cards(st.session_state["home_movies"])
    else:
        st.info("No movies are available to show yet.")

    if st.session_state["home_movies_have_more"]:
        st.button(
            "Load More Movies",
            key="home_load_more_movies",
            on_click=_load_next_home_movie_batch,
            type="secondary",
        )
