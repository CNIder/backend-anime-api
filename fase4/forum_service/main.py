from flask import Flask, request
from flask_restful import Resource, Api
import logging
import csv

app = Flask(__name__)
api = Api(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForumService")

posts = []
post_id_counter = 1
comments = []
comment_id_counter = 1

def load_posts_from_csv():
    global posts, post_id_counter

    try:
        with open('posts.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                post = {
                    "id": int(row["id"]),
                    "user_id": int(row["user_id"]),
                    "title": row["title"],
                    "content": row["content"]
                }
                posts.append(post)

            if posts:
                post_id_counter = max(p["id"] for p in posts) + 1

        logger.info("Posts loaded from CSV")

    except FileNotFoundError:
        logger.warning("posts.csv not found")


def load_comments_from_csv():
    global comments, comment_id_counter

    try:
        with open('comments.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                parent_id = row["parent_comment_id"].strip()
                
                comment = {
                    "id": int(row["id"]),
                    "post_id": int(row["post_id"]),
                    "user_id": int(row["user_id"]),
                    "content": row["content"],
                    "parent_comment_id": int(parent_id) if parent_id else None
                }
                comments.append(comment)

            if comments:
                comment_id_counter = max(c["id"] for c in comments) + 1

        logger.info("Comments loaded from CSV")

    except FileNotFoundError:
        logger.warning("comments.csv not found")


class PostList(Resource):
    def get(self):
        return posts

    def post(self):
        global post_id_counter
        data = request.json

        # validação básica
        required = ["user_id", "title", "content"]
        for field in required:
            if field not in data:
                return {"error": f"{field} is required"}, 400

        post = {
            "id": post_id_counter,
            "user_id": data["user_id"],
            "title": data["title"],
            "content": data["content"]
        }

        post_id_counter += 1
        posts.append(post)

        logger.info(f"Post created: {post}")

        return post, 201


class CommentList(Resource):
    def get(self, post_id):
        filtered_comments = [c for c in comments if c["post_id"] == post_id]
        return filtered_comments, 200
    
    def post(self, post_id):
        global comment_id_counter
        data = request.json

        required = ["user_id", "content"]
        for field in required:
            if field not in data:
                return {"error": f"{field} is required"}, 400

        comment = {
            "id": comment_id_counter,
            "post_id": post_id,
            "user_id": data["user_id"],
            "content": data["content"],
            "parent_comment_id": data.get("parent_comment_id")  # chave aqui
        }

        comment_id_counter += 1
        comments.append(comment)

        return comment, 201


class Post(Resource):
    def get(self, id):
        for p in posts:
            if p["id"] == id:
                return p
        return {"error": "Post not found"}, 404

    def delete(self, id):
        global posts
        posts = [p for p in posts if p["id"] != id]
        return {"message": "Post deleted"}


api.add_resource(PostList, '/posts')
api.add_resource(Post, '/posts/<int:id>')
api.add_resource(CommentList, '/posts/<int:post_id>/comments')

#para testar mais rapidamente
@app.route("/")
def home():
    return {"service": "forum", "status": "ok"}

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    load_posts_from_csv()
    load_comments_from_csv()
    app.run(host='0.0.0.0', port=5002)