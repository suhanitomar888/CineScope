"""Interactive K-Means clustering page."""

import pandas as pd
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from database import db


def render_ml_page():
    st.title("Movie clustering")
    st.caption("Explore groups of movies based on their audience ratings.")
    st.markdown(
        "K-Means groups movies using two features: **average rating** and **number of ratings**. "
        "Standardizing the features puts them on a comparable scale."
    )

    if not st.button("Run K-Means clustering", type="primary"):
        return

    with st.spinner("Training the clustering model..."):
        pipeline = [
            {
                "$group": {
                    "_id": "$movieId",
                    "avg_rating": {"$avg": "$rating"},
                    "rating_count": {"$sum": 1},
                }
            }
        ]
        movie_stats = list(db.ratings.aggregate(pipeline))

        if len(movie_stats) < 4:
            st.error("At least four movies with ratings are needed for clustering.")
            return

        df = pd.DataFrame(movie_stats)
        features = df[["avg_rating", "rating_count"]]
        scaled_features = StandardScaler().fit_transform(features)
        model = KMeans(n_clusters=4, random_state=42, n_init=10)
        df["cluster"] = model.fit_predict(scaled_features)

        cluster_count = df["cluster"].nunique()
        if 2 <= cluster_count < len(df):
            score_text = f"{silhouette_score(scaled_features, df['cluster']):.4f}"
        else:
            score_text = "Not available"

    st.success("K-Means model trained successfully.")
    metric_columns = st.columns(2)
    metric_columns[0].metric("Configured clusters", "4")
    metric_columns[1].metric("Silhouette score", score_text)
    st.caption("A higher silhouette score generally means the groups are more distinct.")

    st.subheader("Cluster distribution")
    cluster_counts = df["cluster"].value_counts().sort_index()
    st.bar_chart(cluster_counts)

    st.subheader("Sample cluster results")
    st.caption("First 20 movie rating summaries and their assigned cluster.")
    st.dataframe(df.head(20), use_container_width=True, hide_index=True)
