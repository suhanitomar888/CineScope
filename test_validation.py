"""to confirm that MongoDB actually rejects invalid documents,
rather than only confirming that the validation rules were configured."""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import WriteError

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["cinescope"]

try:
    db.movies.insert_one({
        "movieId": 999998,
        "genres": ["Drama"]
    })

    print("ERROR: Invalid movie was accepted")

except WriteError:
    print("SUCCESS: Invalid movie rejected by validation")

finally:
    client.close()
