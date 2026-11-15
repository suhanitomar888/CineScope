
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["cinescope"]


def add_validation(collection_name, schema):
    db.command({
        "collMod": collection_name,
        "validator": {"$jsonSchema": schema},
        "validationLevel": "strict",
        "validationAction": "error"
    })

    print(f"Validation added to {collection_name}")


movie_schema = {
    "bsonType": "object",
    "required": ["movieId", "title", "genres"],
    "properties": {
        "movieId": {"bsonType": "int"},
        "title": {"bsonType": "string"},
        "genres": {
            "bsonType": "array",
            "items": {"bsonType": "string"}
        }
    }
}

rating_schema = {
    "bsonType": "object",
    "required": ["userId", "movieId", "rating", "timestamp"],
    "properties": {
        "userId": {"bsonType": "int"},
        "movieId": {"bsonType": "int"},
        "rating": {
            "bsonType": ["double", "int", "decimal"],
            "minimum": 0.5,
            "maximum": 5
        },
        "timestamp": {"bsonType": "date"}
    }
}


tag_schema = {
    "bsonType": "object",
    "required": ["userId", "movieId", "tag", "timestamp"],
    "properties": {
        "userId": {"bsonType": "int"},
        "movieId": {"bsonType": "int"},
        "tag": {"bsonType": "string"},
        "timestamp": {"bsonType": "date"}
    }
}

try:
    add_validation("movies", movie_schema)
    add_validation("ratings", rating_schema)
    add_validation("tags", tag_schema)

finally:
    client.close()
