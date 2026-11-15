
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["cinescope"]

try:
    explanation = db.movies.find(
        {"title": "Toy Story (1995)"}
    ).explain()

    print("Winning query plan:")
    print(explanation["queryPlanner"]["winningPlan"])

    print(
        "\nDocuments examined:",
        explanation["executionStats"]["totalDocsExamined"]
    )

    print(
        "Index keys examined:",
        explanation["executionStats"]["totalKeysExamined"]
    )

finally:
    client.close()
