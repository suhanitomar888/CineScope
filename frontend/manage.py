"""Add, update, and delete movie records."""

import re
from difflib import SequenceMatcher
from html import escape

import streamlit as st
from pymongo.errors import DuplicateKeyError

from database import db
from frontend.auth import is_admin, require_admin
from frontend.movie_cards import (
    _poster_bytes,
    get_tmdb_movie_details,
    search_tmdb_movies,
    tmdb_poster_url,
)

_PENDING_ADD_KEY = "manage_pending_movie_add"
_UPDATE_RESULTS_KEY = "manage_update_movie_results"
_DELETE_RESULTS_KEY = "manage_delete_movie_results"


def _normalize_title(title):
    """Normalize a movie title for strict matching against TMDB results."""
    title = re.sub(r"\s*\(\d{4}\)\s*$", "", str(title or ""))
    return re.sub(r"[^a-z0-9]", "", title.casefold())


def _year_from_title(title):
    match = re.search(r"\((\d{4})\)\s*$", str(title or ""))
    return match.group(1) if match else ""


def _rank_tmdb_matches(title, results):
    """Choose a uniquely strong title match or return options for user review."""
    normalized_title = _normalize_title(title)
    requested_year = _year_from_title(title)
    ranked = []
    for result in results:
        names = [result.get("title", ""), result.get("original_title", "")]
        score = max(
            (SequenceMatcher(None, normalized_title, _normalize_title(name)).ratio() for name in names),
            default=0,
        )
        release_date = str(result.get("release_date") or "")
        ranked.append((score, result, release_date[:4]))

    ranked.sort(key=lambda item: (item[0], item[2] == requested_year), reverse=True)
    exact = [item for item in ranked if item[0] == 1.0]

    if requested_year:
        exact_year = [item for item in exact if item[2] == requested_year]
        if len(exact_year) == 1:
            return "matched", exact_year[0][1], []
        if len(exact_year) > 1:
            return "ambiguous", None, [item[1] for item in exact_year[:5]]
    elif len(exact) == 1:
        close_matches = [item for item in ranked if item[0] >= 0.85]
        if len(close_matches) == 1:
            return "matched", exact[0][1], []
    elif len(exact) > 1:
        return "ambiguous", None, [item[1] for item in exact[:5]]

    likely = [item for item in ranked if item[0] >= 0.55]
    if not likely:
        return "no_match", None, []
    if not requested_year and likely[0][0] >= 0.95 and (
        len(likely) == 1 or likely[0][0] - likely[1][0] >= 0.15
    ):
        return "matched", likely[0][1], []
    return "ambiguous", None, [item[1] for item in likely[:5]]


def _insert_new_movie(title, genres, tmdb_details=None):
    """Insert one new movie without changing any existing document."""
    require_admin()
    title = str(title or "").strip()
    genres = [
        genre.strip()
        for genre in (genres if isinstance(genres, list) else [])
        if isinstance(genre, str) and genre.strip()
    ]
    if not title:
        raise ValueError("A movie title is required.")

    tmdb_id = (tmdb_details or {}).get("tmdbId", "")
    duplicate_queries = [
        {"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}}
    ]
    if tmdb_id:
        tmdb_values = [str(tmdb_id)]
        try:
            tmdb_values.append(int(tmdb_id))
        except (TypeError, ValueError):
            pass
        duplicate_queries.append({"tmdbId": {"$in": tmdb_values}})
    existing = db.movies.find_one({"$or": duplicate_queries})
    if existing:
        return {"status": "exists", "movieId": existing.get("movieId")}

    movie = {"title": title, "genres": genres}
    if tmdb_details:
        movie.update(
            {
                "tmdbId": tmdb_details.get("tmdbId", ""),
                "imdbId": tmdb_details.get("imdbId", ""),
                "posterPath": tmdb_details.get("posterPath", ""),
                "releaseDate": tmdb_details.get("releaseDate", ""),
            }
        )
    # The unique movieId index is created by database.setup_database(). Retry
    # if another Admin inserts a movie between finding the maximum and insert.
    for _ in range(5):
        highest_movie = db.movies.find_one(
            {"movieId": {"$type": "number"}},
            sort=[("movieId", -1)],
            projection={"movieId": 1},
        )
        new_movie_id = int(highest_movie["movieId"]) + 1 if highest_movie else 1
        if db.movies.find_one({"movieId": new_movie_id}, projection={"_id": 1}):
            continue
        movie["movieId"] = new_movie_id
        try:
            db.movies.insert_one(movie)
            return {"status": "added", "movieId": new_movie_id}
        except DuplicateKeyError:
            continue
    raise RuntimeError("Could not allocate a unique movie ID. Please retry.")


def _update_movie_record(movie_id, title, genres):
    """Update a movie only for an authenticated Admin session."""
    require_admin()
    title = str(title or "").strip()
    genres = [
        genre.strip()
        for genre in (genres if isinstance(genres, list) else [])
        if isinstance(genre, str) and genre.strip()
    ]
    if not title:
        raise ValueError("A movie title is required.")
    return db.movies.update_one(
        {"movieId": int(movie_id)},
        {"$set": {"title": title, "genres": genres}},
    )


def _delete_movie_record(movie_id, confirmed=False):
    """Delete one movie only for a confirmed, authenticated Admin action."""
    require_admin()
    if confirmed is not True:
        raise ValueError("Explicit confirmation is required before deletion.")
    return db.movies.delete_one({"movieId": int(movie_id)})


def _find_movies_by_title(title):
    """Return a bounded, title-matched list without exposing ObjectIds to UI state."""
    title = str(title or "").strip()
    if not title:
        return []
    projection = {
        "_id": 0,
        "movieId": 1,
        "title": 1,
        "genres": 1,
        "releaseDate": 1,
        "tmdbId": 1,
        "imdbId": 1,
    }
    return list(
        db.movies.find(
            {"title": {"$regex": re.escape(title), "$options": "i"}},
            projection,
        ).sort("title", 1).limit(50)
    )


def _movie_genres_text(movie):
    genres = movie.get("genres")
    if isinstance(genres, list):
        return ", ".join(g.strip() for g in genres if isinstance(g, str) and g.strip())
    return genres.strip() if isinstance(genres, str) else ""


def _movie_release_year(movie):
    year = _year_from_title(movie.get("title", ""))
    if year:
        return year
    release_date = str(movie.get("releaseDate") or "")
    return release_date[:4] if re.match(r"^\d{4}", release_date) else "Year unavailable"


def _movie_option_label(movie):
    return f"{movie.get('title', 'Untitled')} ({_movie_release_year(movie)}) · Movie ID {movie.get('movieId')}"


def _show_add_result(result):
    if result["status"] == "added":
        st.success(f"Movie added successfully with ID {result['movieId']}.")
    elif result["status"] == "exists":
        st.warning(f"This movie is already in CineScope (MovieLens ID {result['movieId']}).")


def _search_and_add(title, genre_text):
    """Search TMDB, adding a strong match or saving options for user review."""
    require_admin()
    title = title.strip()
    genres = [genre.strip() for genre in genre_text.split(",") if genre.strip()]
    search_title = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    search = search_tmdb_movies(search_title)
    if search["status"] != "ok":
        st.session_state[_PENDING_ADD_KEY] = {
            "title": title,
            "genres": genres,
            "status": search["status"],
            "candidates": [],
        }
        return

    match_status, match, candidates = _rank_tmdb_matches(title, search["results"])
    if match_status == "matched":
        details = get_tmdb_movie_details(match.get("id"))
        if details["status"] == "ok":
            try:
                _show_add_result(_insert_new_movie(title, genres, details["movie"]))
            except Exception:
                st.error("Could not add the movie. Please check the database connection and try again.")
            return
        st.session_state[_PENDING_ADD_KEY] = {
            "title": title,
            "genres": genres,
            "status": details["status"],
            "candidates": [],
        }
        return

    st.session_state[_PENDING_ADD_KEY] = {
        "title": title,
        "genres": genres,
        "status": match_status,
        "candidates": candidates,
    }


def _add_without_tmdb(pending):
    require_admin()
    try:
        result = _insert_new_movie(pending["title"], pending["genres"])
        _show_add_result(result)
    except Exception:
        st.error("Could not add the movie. Please check the database connection and try again.")
    st.session_state.pop(_PENDING_ADD_KEY, None)


def _render_pending_movie_matches():
    pending = st.session_state.get(_PENDING_ADD_KEY)
    if not pending:
        return

    status = pending["status"]
    if status == "ambiguous":
        st.info("Several TMDB movies are similar. Choose the correct title and year below.")
        for index, candidate in enumerate(pending["candidates"]):
            release_date = str(candidate.get("release_date") or "")
            release_year = release_date[:4] or "Release year unavailable"
            candidate_title = str(candidate.get("title") or candidate.get("original_title") or "Untitled")
            poster_url = tmdb_poster_url(candidate.get("poster_path"), "w185")
            poster_bytes = _poster_bytes(poster_url)
            with st.container(border=True):
                poster_column, detail_column = st.columns([1, 4])
                with poster_column:
                    if poster_bytes:
                        st.image(poster_bytes, width=100, alt=f"{candidate_title} poster")
                    else:
                        st.caption("No poster available")
                with detail_column:
                    st.markdown(f"**{escape(candidate_title)} ({escape(release_year)})**")
                    overview = str(candidate.get("overview") or "").strip()
                    if overview:
                        st.caption(overview[:220] + ("..." if len(overview) > 220 else ""))
                    if st.button(
                        "Select this movie",
                        key=f"select_tmdb_movie_{candidate.get('id')}_{index}",
                    ):
                        details = get_tmdb_movie_details(candidate.get("id"))
                        if details["status"] == "ok":
                            try:
                                result = _insert_new_movie(
                                    pending["title"], pending["genres"], details["movie"]
                                )
                                _show_add_result(result)
                            except Exception:
                                st.error("Could not add the movie. Please check the database connection and try again.")
                            st.session_state.pop(_PENDING_ADD_KEY, None)
                        else:
                            pending["status"] = details["status"]
                            pending["candidates"] = []
                            st.session_state[_PENDING_ADD_KEY] = pending
                            st.warning("TMDB details could not be loaded. You can add it without external IDs.")
    elif status == "no_match":
        st.info("No reliable TMDB title match was found. You can add the movie without external IDs.")
    elif status == "missing_key":
        st.warning("TMDB_API_KEY is not configured. You can still add the movie without external IDs.")
    elif status == "invalid_key":
        st.warning("TMDB rejected the configured API key. You can still add the movie without external IDs.")
    else:
        st.warning("TMDB is unavailable right now. You can still add the movie without external IDs.")

    if st.session_state.get(_PENDING_ADD_KEY) and st.button(
        "Add without TMDB details",
        key="add_movie_without_tmdb",
        type="secondary",
    ):
        _add_without_tmdb(st.session_state[_PENDING_ADD_KEY])


def render_manage():
    if not is_admin():
        st.error("Admin access is required to manage movies.")
        return

    st.title("Manage movies")
    st.caption("Create, update, and remove movie records in your collection.")

    add_tab, update_tab, delete_tab = st.tabs(["Add movie", "Update movie", "Delete movie"])

    with add_tab:
        st.subheader("Add a new movie")
        with st.form("add_movie_form"):
            title = st.text_input("Movie title")
            genres = st.text_input("Genres", placeholder="Drama, Romance")
            submitted = st.form_submit_button("Search TMDB and add", type="primary")
            if submitted:
                st.session_state.pop(_PENDING_ADD_KEY, None)
                if not title.strip():
                    st.error("Please enter a movie title.")
                else:
                    _search_and_add(title, genres)
        _render_pending_movie_matches()

    with update_tab:
        st.subheader("Update movie details")
        with st.form("update_movie_search_form"):
            update_query = st.text_input(
                "Search movie title", key="manage_update_search_input"
            )
            update_search = st.form_submit_button("Search movies")
        if update_search:
            st.session_state[_UPDATE_RESULTS_KEY] = _find_movies_by_title(update_query)
            st.session_state["manage_update_generation"] = st.session_state.get(
                "manage_update_generation", 0
            ) + 1

        update_results = st.session_state.get(_UPDATE_RESULTS_KEY, [])
        if update_results:
            generation = st.session_state.get("manage_update_generation", 0)
            update_id = st.selectbox(
                "Matching movies",
                options=[movie["movieId"] for movie in update_results],
                format_func=lambda movie_id: _movie_option_label(
                    next(movie for movie in update_results if movie["movieId"] == movie_id)
                ),
                key=f"manage_update_selected_{generation}",
            )
            selected_movie = next(
                movie for movie in update_results if movie["movieId"] == update_id
            )
            with st.form(f"update_movie_form_{update_id}"):
                new_title = st.text_input(
                    "Movie title",
                    value=str(selected_movie.get("title") or ""),
                    key=f"manage_update_title_{update_id}",
                )
                new_genres = st.text_input(
                    "Genres (comma separated)",
                    value=_movie_genres_text(selected_movie),
                    key=f"manage_update_genres_{update_id}",
                )
                update_button = st.form_submit_button("Save changes", type="primary")
                if update_button:
                    try:
                        result = _update_movie_record(
                            update_id,
                            new_title,
                            [genre.strip() for genre in new_genres.split(",") if genre.strip()],
                        )
                        if result.matched_count:
                            st.success("Movie updated. Its Movie ID, ratings, tags, and external IDs were preserved.")
                            st.session_state[_UPDATE_RESULTS_KEY] = _find_movies_by_title(
                                update_query
                            )
                        else:
                            st.warning("The selected movie could not be found.")
                    except Exception:
                        st.error("Update failed. Please check the database connection and try again.")
        elif _UPDATE_RESULTS_KEY in st.session_state:
            st.info("No matching movies were found.")

    with delete_tab:
        st.subheader("Delete a movie")
        with st.form("delete_movie_search_form"):
            delete_query = st.text_input(
                "Search movie title", key="manage_delete_search_input"
            )
            delete_search = st.form_submit_button("Search movies")
        if delete_search:
            st.session_state[_DELETE_RESULTS_KEY] = _find_movies_by_title(delete_query)
            st.session_state["manage_delete_generation"] = st.session_state.get(
                "manage_delete_generation", 0
            ) + 1

        delete_results = st.session_state.get(_DELETE_RESULTS_KEY, [])
        if delete_results:
            generation = st.session_state.get("manage_delete_generation", 0)
            delete_id = st.selectbox(
                "Matching movies",
                options=[movie["movieId"] for movie in delete_results],
                format_func=lambda movie_id: _movie_option_label(
                    next(movie for movie in delete_results if movie["movieId"] == movie_id)
                ),
                key=f"manage_delete_selected_{generation}",
            )
            selected_movie = next(
                movie for movie in delete_results if movie["movieId"] == delete_id
            )
            st.markdown(f"**Selected:** {_movie_option_label(selected_movie)}")
            st.caption(f"Genres: {_movie_genres_text(selected_movie) or 'Not listed'}")
            st.warning(
                "Deleting a movie removes only its document from the movies collection. "
                "Associated ratings and tags will remain in their collections."
            )
            with st.form(f"delete_movie_form_{delete_id}"):
                confirm_delete = st.checkbox(
                    "I understand and confirm deletion.",
                    key=f"manage_delete_confirm_{delete_id}",
                )
                delete_button = st.form_submit_button("Delete selected movie", type="primary")
                if delete_button:
                    if not confirm_delete:
                        st.warning("Please confirm before deleting.")
                    else:
                        try:
                            result = _delete_movie_record(delete_id, confirmed=True)
                        except Exception:
                            st.error("Delete failed. Please check the database connection and try again.")
                            return
                        if result.deleted_count:
                            st.success("Selected movie deleted successfully.")
                            st.session_state[_DELETE_RESULTS_KEY] = [
                                movie for movie in delete_results
                                if movie.get("movieId") != delete_id
                            ]
                        else:
                            st.warning("The selected movie could not be found.")
        elif _DELETE_RESULTS_KEY in st.session_state:
            st.info("No matching movies were found.")
