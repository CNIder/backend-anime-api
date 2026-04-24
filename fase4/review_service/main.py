from flask import Flask, request
from flask_restful import Resource, Api
import logging

app = Flask(__name__)
api = Api(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReviewService")

reviews = []
review_id_counter = 1


class ReviewList(Resource):
    def get(self):
        anime_id = request.args.get("anime_id")

        if anime_id is not None:
            anime_id = int(anime_id)
            return [r for r in reviews if r["anime_id"] == anime_id]

        return reviews

    def post(self):
        global review_id_counter
        data = request.json

        # validação básica
        required = ["user_id", "anime_id", "rating"]
        for field in required:
            if field not in data:
                return {"error": f"{field} is required"}, 400

        review = {
            "id": review_id_counter,
            "user_id": data["user_id"],
            "anime_id": data["anime_id"],
            "rating": data["rating"],
            "comment": data.get("comment", "")
        }

        review_id_counter += 1
        reviews.append(review)

        logger.info(f"Review created: {review}")

        return review, 201


class Review(Resource):
    def get(self, id):
        for r in reviews:
            if r["id"] == id:
                return r
        return {"error": "Review not found"}, 404

    def put(self, id):
        data = request.json

        for r in reviews:
            if r["id"] == id:
                r["rating"] = data.get("rating", r["rating"])
                r["comment"] = data.get("comment", r["comment"])
                return r

        return {"error": "Review not found"}, 404

    def delete(self, id):
        global reviews
        reviews = [r for r in reviews if r["id"] != id]
        return {"message": "Review deleted"}


api.add_resource(ReviewList, '/posts')
api.add_resource(Review, '/posts/<int:id>')

#para testar mais rapidamente
@app.route("/")
def home():
    return {"service": "review", "status": "ok"}

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)