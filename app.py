from flask import Flask, send_file, Response
from flask_cors import CORS


app = Flask(__name__)
CORS(app)


def generate():
    video_path = "data/sample.mp4"
    with open(video_path, "rb") as video_file:
        while chunk := video_file.read(4096):
            yield chunk


@app.route("/api/video")
def get_video():
    video_path = "data/sample.mp4"
    return send_file(video_path, mimetype="video/mp4")


@app.route("/api/film")
def get_film_data():
    # This function can be used to fetch film data if needed
    return {
        "title": "Beneath the Horizon",
        "director": "Ava Richardson",
        "year": 2024,
        "description": "In a remote coastal village, a young scientist uncovers a series of ancient signals beneath the ocean floor. As the mystery unfolds, she must confront the boundaries of science, history, and faith.",
        "genre": "Science Fiction, Mystery",
        "duration": 112,
        "language": "English",
        "tags": ["sci-fi", "mystery", "female-lead", "ocean", "indie film"],
    }


@app.route("/api/video/stream")
def stream_video():
    return Response(generate(), mimetype="video/mp4")


if __name__ == "__main__":
    app.run(debug=True)
