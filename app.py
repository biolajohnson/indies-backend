from flask import Flask, send_file, Response
from flask_cors import CORS


app = Flask(__name__)
CORS(app)


def generate():
    video_path = 'data/sample.mp4'
    with open(video_path, 'rb') as video_file:
        while chunk := video_file.read(4096):
            yield chunk

@app.route('/video')
def get_video():
    video_path = 'data/sample.mp4'
    return send_file(video_path, mimetype='video/mp4')


@app.route('/video/stream')
def stream_video():
    return Response(generate(), mimetype="video/mp4")

if __name__ == '__main__':
    app.run(debug=True)