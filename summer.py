from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# ------------------ CONFIGURATION ------------------

# Filesystem folder for profile photo uploads
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ------------------ CONNECT TO MONGODB ------------------

try:
    client = MongoClient("mongodb+srv://khebbabmohamed5:chanpanzi@summer.wkal298.mongodb.net/")
    db = client["summer"]
    users_collection = db["User"]
    posts_collection = db["Post"]
    print("Connected to MongoDB")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

# ------------------ HELPER FUNCTIONS ------------------

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------ ROUTES ------------------

@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Welcome to the Summer API!", "status": "running"})

# ------ SIGNUP ------
@app.route("/auth/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        required_fields = ['first_name', 'last_name', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        if not validate_email(data['email']):
            return jsonify({"error": "Invalid email format"}), 400

        if len(data['password']) < 6:
            return jsonify({"error": "Password must be at least 6 characters long"}), 400

        existing_user = users_collection.find_one({"email": data['email'].lower().strip()})
        if existing_user:
            return jsonify({"error": "User with this email already exists"}), 409

        hashed_pw = generate_password_hash(data['password'])
        user_data = {
            "first_name": data['first_name'].strip(),
            "last_name": data['last_name'].strip(),
            "email": data['email'].lower().strip(),
            "password": hashed_pw,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "is_active": True
        }

        result = users_collection.insert_one(user_data)

        return jsonify({
            "message": "User created successfully",
            "user_id": str(result.inserted_id),
            "user": {
                "id": str(result.inserted_id),
                "first_name": user_data['first_name'],
                "last_name": user_data['last_name'],
                "email": user_data['email']
            }
        }), 201

    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ LOGIN ------
@app.route("/auth/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data.get('email') or not data.get('password'):
            return jsonify({"error": "Email and password are required"}), 400

        user = users_collection.find_one({"email": data['email'].lower().strip()})
        if not user or not check_password_hash(user['password'], data['password']):
            return jsonify({"error": "Invalid email or password"}), 401

        if not user.get('is_active', True):
            return jsonify({"error": "Account is deactivated"}), 401

        users_collection.update_one(
            {"_id": user['_id']},
            {"$set": {"last_login": datetime.now(timezone.utc)}}
        )

        return jsonify({
            "message": "Login successful",
            "user": {
                "id": str(user['_id']),
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "email": user['email']
            }
        }), 200

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ LOGOUT ------
@app.route("/auth/logout", methods=["POST"])
def logout():
    try:
        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ GET SINGLE USER PROFILE ------
@app.route("/auth/user/<user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user_obj = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user_obj:
            return jsonify({"error": "User not found"}), 404

        user_data = {
            "id": str(user_obj["_id"]),
            "first_name": user_obj["first_name"],
            "last_name": user_obj["last_name"],
            "email": user_obj["email"],
            "photo_url": user_obj.get("photo_url", None),
            "created_at": user_obj.get("created_at").isoformat() if user_obj.get("created_at") else None,
            "updated_at": user_obj.get("updated_at").isoformat() if user_obj.get("updated_at") else None,
        }
        return jsonify({"user": user_data}), 200
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ UPDATE USER PROFILE ------
@app.route("/auth/user/<user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        update_fields = {}

        if "first_name" in data:
            first_name = data["first_name"].strip()
            if not first_name:
                return jsonify({"error": "First name cannot be empty"}), 400
            update_fields["first_name"] = first_name

        if "last_name" in data:
            last_name = data["last_name"].strip()
            if not last_name:
                return jsonify({"error": "Last name cannot be empty"}), 400
            update_fields["last_name"] = last_name

        if "email" in data:
            new_email = data["email"].lower().strip()
            if not validate_email(new_email):
                return jsonify({"error": "Invalid email format"}), 400
            existing = users_collection.find_one({
                "email": new_email,
                "_id": {"$ne": ObjectId(user_id)}
            })
            if existing:
                return jsonify({"error": "Email already in use"}), 409
            update_fields["email"] = new_email

        if "password" in data and data["password"].strip() != "":
            pwd = data["password"].strip()
            if len(pwd) < 6:
                return jsonify({"error": "Password must be at least 6 characters"}), 400
            update_fields["password"] = generate_password_hash(pwd)

        if not update_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        update_fields["updated_at"] = datetime.now(timezone.utc)

        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_fields},
        )

        if result.matched_count == 0:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"Update user error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ UPLOAD PROFILE PHOTO ------
@app.route("/auth/user/<user_id>/photo", methods=["POST"])
def upload_photo(user_id):
    try:
        user_obj = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user_obj:
            return jsonify({"error": "User not found"}), 404

        if 'photo' not in request.files:
            return jsonify({"error": "No file part in request"}), 400

        file = request.files["photo"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(f"{user_id}_{datetime.now().timestamp()}_{file.filename}")
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)

            photo_url = request.host_url.rstrip('/') + '/static/uploads/' + filename

            users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"photo_url": photo_url, "updated_at": datetime.now(timezone.utc)}}
            )

            return jsonify({"success": True, "photo_url": photo_url}), 200
        else:
            return jsonify({"error": "File type not allowed"}), 400

    except Exception as e:
        print(f"Upload photo error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ SERVE UPLOADED FILES ------
@app.route("/static/uploads/<filename>")
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ------ CREATE POST ------
@app.route("/posts", methods=["POST"])
def create_post():
    try:
        data = request.get_json()
        if not data.get('user_id'):
            return jsonify({"error": "User ID is required"}), 400
        if not data.get('content'):
            return jsonify({"error": "Post content is required"}), 400

        user = users_collection.find_one({"_id": ObjectId(data['user_id'])})
        if not user:
            return jsonify({"error": "User not found"}), 404

        post_data = {
            "user_id": ObjectId(data['user_id']),
            "content": data['content'].strip(),
            "likes": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "liked_by": []
        }

        result = posts_collection.insert_one(post_data)

        return jsonify({
            "message": "Post created successfully",
            "post_id": str(result.inserted_id),
            "post": {
                "id": str(result.inserted_id),
                "content": post_data['content'],
                "likes": post_data['likes'],
                "created_at": post_data['created_at'].isoformat(),
                "user": {
                    "first_name": user['first_name'],
                    "last_name": user['last_name']
                }
            }
        }), 201

    except Exception as e:
        print(f"Create post error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ GET POSTS ------
@app.route("/posts", methods=["GET"])
def get_posts():
    try:
        sort_by = request.args.get('sort', 'new')
        if sort_by == 'old':
            sort_criteria = [("created_at", 1)]
        elif sort_by == 'likes':
            sort_criteria = [("likes", -1), ("created_at", -1)]
        else:
            sort_criteria = [("created_at", -1)]

        pipeline = [
            {
                "$lookup": {
                    "from": "User",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            {"$unwind": "$user_info"},
            {
                "$project": {
                    "_id": 1,
                    "content": 1,
                    "likes": 1,
                    "created_at": 1,
                    "liked_by": 1,
                    "user_first_name": "$user_info.first_name",
                    "user_last_name": "$user_info.last_name"
                }
            },
            {"$sort": dict(sort_criteria)}
        ]

        posts = list(posts_collection.aggregate(pipeline))
        formatted_posts = []
        for post in posts:
            formatted_posts.append({
                "id": str(post['_id']),
                "content": post['content'],
                "likes": post['likes'],
                "created_at": post['created_at'].isoformat(),
                "user": {
                    "first_name": post['user_first_name'],
                    "last_name": post['user_last_name']
                },
                "liked_by": [str(uid) for uid in post.get('liked_by', [])]
            })

        return jsonify({
            "posts": formatted_posts,
            "count": len(formatted_posts),
            "sort": sort_by
        }), 200

    except Exception as e:
        print(f"Get posts error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------ TOGGLE LIKE ------
@app.route("/posts/<post_id>/like", methods=["POST"])
def toggle_like(post_id):
    try:
        data = request.get_json()
        if not data.get('user_id'):
            return jsonify({"error": "User ID is required"}), 400

        user_id = ObjectId(data['user_id'])
        post_obj_id = ObjectId(post_id)

        post = posts_collection.find_one({"_id": post_obj_id})
        if not post:
            return jsonify({"error": "Post not found"}), 404

        liked_by = post.get('liked_by', [])
        if user_id in liked_by:
            posts_collection.update_one(
                {"_id": post_obj_id},
                {
                    "$pull": {"liked_by": user_id},
                    "$inc": {"likes": -1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            action = "unliked"
            new_likes = post['likes'] - 1
        else:
            posts_collection.update_one(
                {"_id": post_obj_id},
                {
                    "$push": {"liked_by": user_id},
                    "$inc": {"likes": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            action = "liked"
            new_likes = post['likes'] + 1

        return jsonify({
            "message": f"Post {action} successfully",
            "action": action,
            "likes": new_likes
        }), 200

    except Exception as e:
        print(f"Toggle like error: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000)) 
    app.run(debug=True, host="0.0.0.0", port=port)
