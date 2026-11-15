"""Shared movie cards and CineScope rating lookup for Home and Browse."""

import base64
import hashlib
import os
import re
import time
from html import escape

import requests
import streamlit as st
from dotenv import load_dotenv

from database import db

load_dotenv()
_TMDB_SESSION = requests.Session()


class _PosterLookupError(Exception):
    """A temporary TMDB movie-details request failure."""


def _request_with_retries(url, headers=None, params=None):
    """Retry short-lived TLS, connection, throttling, and server failures."""
    last_error = None
    for attempt in range(5):
        try:
            response = _TMDB_SESSION.get(
                url, headers=headers, params=params, timeout=10
            )
            if response.status_code != 429 and response.status_code < 500:
                return response
            last_error = requests.HTTPError(f"Temporary HTTP {response.status_code}")
        except requests.RequestException as error:
            last_error = error
        if attempt < 4:
            time.sleep(0.25 * (attempt + 1))
    raise last_error


def _tmdb_auth_headers():
    """Return TMDB request headers without exposing the token to callers."""
    token = os.getenv("TMDB_API_KEY")
    if not token:
        return None
    return {"Authorization": f"Bearer {token.strip()}", "accept": "application/json"}


def search_tmdb_movies(title):
    """Search TMDB and return a safe status plus candidate movie documents."""
    headers = _tmdb_auth_headers()
    if not headers:
        return {"status": "missing_key", "results": []}

    try:
        response = _request_with_retries(
            "https://api.themoviedb.org/3/search/movie",
            headers=headers,
            params={"query": title, "include_adult": "false", "language": "en-US", "page": 1},
        )
        if response.status_code in (401, 403):
            return {"status": "invalid_key", "results": []}
        response.raise_for_status()
        results = response.json().get("results", [])
        return {"status": "ok", "results": results if isinstance(results, list) else []}
    except (requests.RequestException, ValueError, TypeError):
        return {"status": "unavailable", "results": []}


def get_tmdb_movie_details(tmdb_id):
    """Fetch IDs, poster path, and release date for a selected TMDB movie."""
    headers = _tmdb_auth_headers()
    if not headers:
        return {"status": "missing_key", "movie": None}

    try:
        response = _request_with_retries(
            f"https://api.themoviedb.org/3/movie/{int(tmdb_id)}",
            headers=headers,
        )
        if response.status_code == 404:
            return {"status": "not_found", "movie": None}
        if response.status_code in (401, 403):
            return {"status": "invalid_key", "movie": None}
        response.raise_for_status()
        details = response.json()
        return {
            "status": "ok",
            "movie": {
                "tmdbId": str(details.get("id", tmdb_id)),
                "imdbId": details.get("imdb_id") or "",
                "posterPath": details.get("poster_path") or "",
                "releaseDate": details.get("release_date") or "",
            },
        }
    except (requests.RequestException, ValueError, TypeError):
        return {"status": "unavailable", "movie": None}


def tmdb_poster_url(poster_path, size="w500"):
    """Build a TMDB image URL from a valid poster path."""
    if not isinstance(poster_path, str) or not poster_path.startswith("/"):
        return None
    if poster_path.startswith("//"):
        return None
    return f"https://image.tmdb.org/t/p/{size}{poster_path}"


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_tmdb_image_bytes(image_url):
    """Fetch and cache a poster so Streamlit serves it from the app origin."""
    try:
        response = _request_with_retries(image_url)
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("image/"):
            raise _PosterLookupError("TMDB poster response was not an image")
        if not response.content:
            raise _PosterLookupError("TMDB returned an empty poster")
        return response.content
    except requests.RequestException as error:
        raise _PosterLookupError("TMDB poster image request failed") from error


def _poster_bytes(image_url):
    if not image_url:
        return None
    try:
        return _fetch_tmdb_image_bytes(image_url)
    except _PosterLookupError:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_tmdb_poster_url_v4(tmdb_id, credential_fingerprint):
    """Fetch and cache the hosted poster URL from TMDB movie details."""
    token = os.getenv("TMDB_API_KEY")
    if not token:
        return None

    try:
        movie_response = _request_with_retries(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            {
                "Authorization": f"Bearer {token.strip()}",
                "accept": "application/json",
            },
        )
        if movie_response.status_code == 404:
            return None
        movie_response.raise_for_status()
        poster_path = movie_response.json().get("poster_path")
        if not isinstance(poster_path, str) or not poster_path.startswith("/"):
            return None

        return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except (requests.RequestException, ValueError, TypeError) as error:
        raise _PosterLookupError("TMDB poster lookup failed") from error


def _poster_image(tmdb_id):
    """Return a hosted poster URL for a valid ID without exposing the API key."""
    normalized_id = str(tmdb_id or "").strip()
    token = os.getenv("TMDB_API_KEY")
    if not normalized_id.isdigit() or not token:
        return None
    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        return _fetch_tmdb_poster_url_v4(normalized_id, fingerprint)
    except _PosterLookupError:
        return None


def _release_year(title):
    """Return a trailing release year and a title without that year, if present."""
    match = re.search(r"\s*\((\d{4})\)\s*$", title)
    if not match:
        return title, "Year unavailable"
    return title[: match.start()].strip(), match.group(1)


def genre_names(value):
    """Keep only non-empty genre strings from possibly incomplete movie data."""
    if not isinstance(value, (list, tuple)):
        return []
    return [genre.strip() for genre in value if isinstance(genre, str) and genre.strip()]


def _external_ids(movie):
    """Build valid external links from the IDs already stored on a movie."""
    tmdb_raw = str(movie.get("tmdbId", "")).strip()
    imdb_raw = str(movie.get("imdbId", "")).strip()

    tmdb_url = (
        f"https://www.themoviedb.org/movie/{tmdb_raw}"
        if tmdb_raw.isdigit()
        else None
    )

    if imdb_raw.lower().startswith("tt") and imdb_raw[2:].isdigit():
        imdb_id = imdb_raw
    elif imdb_raw.isdigit():
        imdb_id = f"tt{imdb_raw}"
    else:
        imdb_id = None
    imdb_url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None

    return tmdb_raw or "Unavailable", imdb_raw or "Unavailable", tmdb_url, imdb_url


def get_rating_summaries(movie_ids):
    """Get average rating and rating count for the requested movie IDs."""
    if not movie_ids:
        return {}

    pipeline = [
        {"$match": {"movieId": {"$in": movie_ids}}},
        {
            "$group": {
                "_id": "$movieId",
                "averageRating": {"$avg": "$rating"},
                "ratingCount": {"$sum": 1},
            }
        },
    ]
    return {
        row["_id"]: {
            "average": row.get("averageRating"),
            "count": row.get("ratingCount", 0),
        }
        for row in db.ratings.aggregate(pipeline)
    }


def _render_card(movie, rating):
    raw_title = str(movie.get("title", "Untitled"))
    title, year = _release_year(raw_title)
    release_date = movie.get("releaseDate")
    if year == "Year unavailable" and isinstance(release_date, str):
        release_year = re.match(r"(\d{4})", release_date)
        if release_year:
            year = release_year.group(1)
    genres = genre_names(movie.get("genres"))
    genre_text = ", ".join(genres) or "Genre not listed"
    movie_id = movie.get("movieId")
    tmdb_id, imdb_id, tmdb_url, imdb_url = _external_ids(movie)

    if rating and rating.get("count", 0):
        average = rating.get("average")
        rating_text = f"{average:.2f} / 5" if average is not None else "Unavailable"
        count_text = f"{rating['count']:,} ratings"
    else:
        rating_text = "Not rated / 5"
        count_text = "No ratings yet"

    safe_title = escape(title)
    safe_year = escape(year)
    safe_genres = escape(genre_text)
    poster_input = movie.get("tmdbId")
    if "posterPath" in movie:
        poster_url = tmdb_poster_url(movie.get("posterPath"))
    else:
        poster_url = _poster_image(poster_input)
    poster_bytes = _poster_bytes(poster_url)
    rating_markup = (
        f'<strong class="cine-rating">{escape(rating_text)}</strong>'
        f'<span class="rating-count">{escape(count_text)}</span>'
    )
    with st.container(border=True):
        with st.container(
            key=f"discovery-poster-{movie_id if movie_id is not None else title}",
            width="stretch",
        ):
            if poster_bytes:
                # Keep the complete poster visible in a proportional 2:3 frame.
                encoded_poster = base64.b64encode(poster_bytes).decode("ascii")
                st.markdown(
                    '<div class="discovery-poster-frame">'
                    f'<img src="data:image/jpeg;base64,{encoded_poster}" alt="{escape(title, quote=True)} movie poster">'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="discovery-poster">'
                    '<span class="poster-orbit"></span>'
                    '<span class="poster-placeholder">POSTER<br>COMING SOON</span>'
                    '<span class="poster-monogram">C</span></div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            '<div class="discovery-card-body">'
            f'<div class="discovery-title-row"><h3>{safe_title}</h3><span>{safe_year}</span></div>'
            f'<p class="discovery-genres">{safe_genres}</p>'
            f'<div class="rating-row"><span class="rating-label">CINESCOPE AVERAGE</span>{rating_markup}</div>'
            '<p class="rating-source">MovieLens ratings stored in CineScope</p>'
            '<div class="external-links">'
            + (
                f'<a class="external-link" href="{escape(tmdb_url, quote=True)}" target="_blank" rel="noopener noreferrer">View on TMDB</a>'
                if tmdb_url
                else '<span class="external-link unavailable-link">TMDB unavailable</span>'
            )
            + (
                f'<a class="external-link" href="{escape(imdb_url, quote=True)}" target="_blank" rel="noopener noreferrer">View on IMDb</a>'
                if imdb_url
                else '<span class="external-link unavailable-link">IMDb unavailable</span>'
            )
            + '</div></div>',
            unsafe_allow_html=True,
        )

        with st.expander("Details"):
            if movie_id is not None:
                st.write(f"**MovieLens ID:** {movie_id}")
            if tmdb_id != "Unavailable":
                st.write(f"**TMDB ID:** {tmdb_id}")
            if imdb_id != "Unavailable":
                st.write(f"**IMDb ID:** {imdb_id}")

def render_movie_cards(movies, columns_per_row=3, rating_summaries=None):
    """Render the same poster card, links, and expandable details on each page."""
    if not movies:
        return

    movie_ids = [movie.get("movieId") for movie in movies if movie.get("movieId") is not None]
    ratings = rating_summaries if rating_summaries is not None else get_rating_summaries(movie_ids)

    for start in range(0, len(movies), columns_per_row):
        row = movies[start : start + columns_per_row]
        columns = st.columns(columns_per_row)
        for column, movie in zip(columns, row):
            with column:
                _render_card(movie, ratings.get(movie.get("movieId")))

    st.markdown(
        '<div class="tmdb-attribution">'
        '<span class="tmdb-credit-label">Credits</span>'
        '<span class="tmdb-logo-wordmark" aria-label="The Movie Database">TMDB</span>'
        '<span>This product uses the TMDB API but is not endorsed or certified by TMDB.</span>'
        '</div>',
        unsafe_allow_html=True,
    )
