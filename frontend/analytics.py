"""MongoDB aggregation results and charts."""

import pandas as pd
import streamlit as st

from database import db


def render_analytics():
    st.title("Movie analytics")
    st.caption("Explore rating and genre patterns in the MovieLens collection.")

    pipeline = [
        {
            "$group": {
                "_id": "$movieId",
                "averageRating": {"$avg": "$rating"},
                "totalRatings": {"$sum": 1},
            }
        },
        {"$match": {"totalRatings": {"$gte": 50}}},
        {"$sort": {"averageRating": -1, "totalRatings": -1}},
        {"$limit": 10},
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
                "title": "$movie.title",
                "averageRating": 1,
                "totalRatings": 1,
            }
        },
    ]
    top_movies = list(db.ratings.aggregate(pipeline))

    st.subheader("Top rated movies")
    st.caption("Movies with at least 50 ratings, ranked by average rating.")
    if top_movies:
        top_df = pd.DataFrame(top_movies)
        st.dataframe(top_df, use_container_width=True, hide_index=True)
        st.bar_chart(top_df.set_index("title")["averageRating"], horizontal=True)
    else:
        st.info("There are not enough ratings to show the top rated movies yet.")

    st.divider()
    st.subheader("Popular genres")
    st.caption("The number of movie records in each genre.")
    genre_data = list(
        db.movies.aggregate(
            [
                {"$unwind": "$genres"},
                {"$group": {"_id": "$genres", "movieCount": {"$sum": 1}}},
                {"$sort": {"movieCount": -1}},
                {"$limit": 10},
            ]
        )
    )
    if genre_data:
        genre_df = pd.DataFrame(genre_data).rename(
            columns={"_id": "Genre", "movieCount": "Movie Count"}
        )
        st.bar_chart(genre_df.set_index("Genre"))
    else:
        st.info("No genre data is available yet.")
