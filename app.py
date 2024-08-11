from flask import Flask, jsonify, request
from amzn_music_meta_api import MusicSession

app = Flask(__name__)

@app.route('/')
async def main():
    url = request.args.get('url')
    if url:
        music_session = MusicSession()
        info = await music_session.get_url_info(url)
        metadata = await music_session.get_metadata(asin=info['asin'], country=info['country'])
        return jsonify(metadata)
    else:
        return "give a url with /?="

if __name__ == "__main__":
    app.run(debug=True)