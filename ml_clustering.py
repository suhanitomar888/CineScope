#Import libraries and connect to MongoDB

import pandas as pd
import numpy as np

from sklearn.preprocessing import StandardScaler, MultiLabelBinarizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from database import db


# Fetch movies from MongoDB
movies = list(db.movies.find({}, {"_id": 0}))

# Fetch ratings from MongoDB
ratings = list(db.ratings.find({}, {"_id": 0}))

# Convert MongoDB documents into DataFrames
movies_df = pd.DataFrame(movies)
ratings_df = pd.DataFrame(ratings)

print("Movies:", movies_df.shape)
print("Ratings:", ratings_df.shape)

print("\nMovies Data:")
print(movies_df.head())

print("\nRatings Data:")
print(ratings_df.head())


# Calculate average rating and total ratings for each movie
pipeline = [
    {
        "$group": {
            "_id": "$movieId",
            "avg_rating": {"$avg": "$rating"},
            "rating_count": {"$sum": 1}
        }
    }
]
movie_stats = list(db.ratings.aggregate(pipeline))

print("\nMovie Statistics:")
for movie in movie_stats[:5]:
    print(movie)

print("\nTotal movies with ratings:", len(movie_stats))


# Prepare data for K-Means

features = []

for movie in movie_stats:
    features.append([
        movie["avg_rating"],
        movie["rating_count"]
    ])

# Scale the features
scaler = StandardScaler()
scaled_features = scaler.fit_transform(features)

# Train K-Means model
kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)

clusters = kmeans.fit_predict(scaled_features)

# Evaluate the model
score = silhouette_score(scaled_features, clusters)

print("\nK-Means Clustering Results:")
print("Number of clusters:", 4)
print("Silhouette Score:", round(score, 4))

for i in range(5):
    print(
        "Movie ID:", movie_stats[i]["_id"],
        "Average Rating:", movie_stats[i]["avg_rating"],
        "Cluster:", clusters[i]
    )

print("\nModel trained successfully!")
