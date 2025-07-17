from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.route('/execute', methods=['POST'])
def execute():
    data = request.json
    return jsonify({"echo": data.get("text", "")})

@app.route("/")
def root_ui():
    return send_from_directory(os.path.join(app.root_path, "../frontend/src"), "index.html")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
