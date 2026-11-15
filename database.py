
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGODB_URI")

if not uri:
    raise ValueError("MONGODB_URI was not found in .env")

client = MongoClient(uri)
db = client["cinescope"]


def setup_database():
    db.movies.create_index("movieId", unique=True)

    db.ratings.create_index(
        [("userId", 1), ("movieId", 1)],
        unique=True
    )

    db.movies.create_index("title")
    db.movies.create_index("genres")
    db.ratings.create_index("movieId")

    print("Indexes created successfully!")


if __name__ == "__main__":
    try:
        setup_database()
    finally:
        client.close()
