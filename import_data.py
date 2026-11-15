
import os
import csv
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

load_dotenv()

uri = os.getenv("MONGODB_URI")

if not uri:
    raise ValueError("MONGODB_URI was not found in .env")

client = MongoClient(uri)
db = client["cinescope"]

dataset_path = r"C:\Users\WELCOME\Desktop\movies_Dataset"


def read_csv(filename):
    file_path = os.path.join(dataset_path, filename)

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


# 1. Prepare movie documents
movies_data = read_csv("movies.csv")
links_data = read_csv("links.csv")

links_by_movie = {
    int(row["movieId"]): row
    for row in links_data
}

movies = []

for row in movies_data:
    movie_id = int(row["movieId"])
    link = links_by_movie.get(movie_id, {})

    genres = (
        []
        if row["genres"] == "(no genres listed)"
        else row["genres"].split("|")
    )

    movies.append({
        "movieId": movie_id,
        "title": row["title"],
        "genres": genres,
        "imdbId": link.get("imdbId", ""),
        "tmdbId": link.get("tmdbId", "")
    })


# 2. Prepare rating documents
ratings_data = read_csv("ratings.csv")
ratings = []

for row in ratings_data:
    ratings.append({
        "userId": int(row["userId"]),
        "movieId": int(row["movieId"]),
        "rating": float(row["rating"]),
        "timestamp": datetime.fromtimestamp(
            int(row["timestamp"]), timezone.utc
        )
    })


# 3. Prepare tag documents
tags_data = read_csv("tags.csv")
tags = []

for row in tags_data:
    tags.append({
        "userId": int(row["userId"]),
        "movieId": int(row["movieId"]),
        "tag": row["tag"],
        "timestamp": datetime.fromtimestamp(
            int(row["timestamp"]), timezone.utc
        )
    })


# 4. Import into MongoDB
try:
    if movies:
        db.movies.insert_many(movies, ordered=False)

    if ratings:
        db.ratings.insert_many(ratings, ordered=False)

    if tags:
        db.tags.insert_many(tags, ordered=False)

    print("Dataset imported successfully!")
    print("Movies:", db.movies.count_documents({}))
    print("Ratings:", db.ratings.count_documents({}))
    print("Tags:", db.tags.count_documents({}))

except BulkWriteError as error:
    print("Some records could not be imported.")
    print(error.details.get("writeErrors", [])[:3])

finally:
    client.close()
