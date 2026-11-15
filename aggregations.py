
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["cinescope"]


def top_rated_movies():
    pipeline = [
        {
            "$group": {
                "_id": "$movieId",
                "averageRating": {"$avg": "$rating"},
                "totalRatings": {"$sum": 1}
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
                "as": "movieDetails"
            }
        },
        {"$unwind": "$movieDetails"},
        {
            "$project": {
                "_id": 0,
                "title": "$movieDetails.title",
                "averageRating": {"$round": ["$averageRating", 2]},
                "totalRatings": 1
            }
        }
    ]

    print("\nTOP 10 MOVIES (minimum 50 ratings)")
    for movie in db.ratings.aggregate(pipeline):
        print(movie)


def genre_statistics():
    pipeline = [
        {"$unwind": "$genres"},
        {
            "$group": {
                "_id": "$genres",
                "movieCount": {"$sum": 1}
            }
        },
        {"$sort": {"movieCount": -1}},
        {"$limit": 10}
    ]

    print("\nTOP 10 GENRES BY MOVIE COUNT")
    for genre in db.movies.aggregate(pipeline):
        print(genre)


if __name__ == "__main__":
    try:
        top_rated_movies()
        genre_statistics()
    finally:
        client.close()