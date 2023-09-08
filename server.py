import requests

from flask import Flask, render_template, send_file, request
from datetime import datetime
from ChunkStorage import ChunkStorage

app = Flask("ChunkQuery-Viewer")
app.template_folder = "viewer"
app.static_folder = "viewer/textures"

PLAYER_NAME = "TheMcSebi"
CHUNK_RADIUS = 12
MAP_RENDER_SIZE = 200
API_SERVER = "127.0.0.1:8090"

chunk_storage = None

@app.route("/")
def route_index():
    return render_template("index.html", size=MAP_RENDER_SIZE, radius=CHUNK_RADIUS, player_name=PLAYER_NAME)

@app.route("/ctrl")
def route_ctrl():
    cookie_expiration = datetime.now().strftime('%a, %d %b %Y %H:%M:%S UTC')
    return render_template("ctrl.html", player_name=PLAYER_NAME, cookie_expiration=cookie_expiration)

@app.route("/status")
def route_status():
    ret = {}
    if chunk_storage is None:
        return {"error": "Chunk storage not initialized"}

    ret["chunk_count"] = len(chunk_storage._data)
    ret["download_queue"] = chunk_storage.download_queue.qsize()
    return ret

@app.route("/save")
def route_save():
    if chunk_storage is None:
        return {"error": "Chunk storage not initialized"}, 400

    chunk_storage.save()
    return {"status": "saved"}

@app.route("/update", methods=["GET", "POST"])
def route_update():
    if chunk_storage is None:
        return {"error": "Chunk storage not initialized"}, 400

    # fetch parameters from POST (json) or GET (url)
    try:
        jsondata = request.json
        player_name = jsondata["player"]
        force_update = jsondata["force"]
    except:
        player_name = request.args.get("player", None)
        force_update = request.args.get("force") is not None

    if player_name is None or len(player_name) == 0:
        return {"error": "No player name given"}, 400

    # check if it's already downloading something
    if chunk_storage.download_queue.qsize() > 0:
        return {"status": f"{chunk_storage.download_queue.qsize()} chunks remaining"}

    # get player location
    try:
        resp = requests.post(f'http://{API_SERVER}/get_player_data', json={"name": player_name})
    except Exception as e:
        return {"error": "Server not running or plugin not enabled", "msg": str(e)}, 500

    try:
        player_data = resp.json()
    except Exception as e:
        return {"error": "Error parsing player location", "msg": str(e)}, 400

    if "error" in player_data:
        return {"error": "Error getting player location", "msg": player_data["error"]}, 500

    # add to download queue
    chunk_storage.load((player_data["cx"], player_data["cz"]), CHUNK_RADIUS, world=player_data["world"], force_update=force_update)

    # add to render queue
    chunk_storage.render((player_data["cx"], player_data["cz"]), CHUNK_RADIUS, world=player_data["world"], player=player_name)

    return {"response": "ok", "player_data": player_data}

@app.route("/heightmap.png", methods=["GET", "POST"])
def route_height():
    # fetch parameters from POST (json) or GET (url)
    try:
        jsondata = request.json
        player_name = jsondata["player"]
    except:
        player_name = request.args.get("player", None)

    if player_name is None or len(player_name) == 0:
        return {"error": "No player name given"}, 400

    # get image from chunk storage
    try:
        img_bytes = chunk_storage.get_image(player_name, "height")
    except:
        return {"error": "Heightmap not generated yet"}, 500

    return send_file(img_bytes, mimetype='image/png')

@app.route("/textures.png", methods=["GET", "POST"])
def route_textures():
    # fetch parameters from POST (json) or GET (url)
    try:
        jsondata = request.json
        player_name = jsondata["player"]
    except:
        player_name = request.args.get("player", None)

    if player_name is None or len(player_name) == 0:
        return {"error": "No player name given"}, 400

    # get image from chunk storage
    try:
        img_bytes = chunk_storage.get_image(player_name, "textures")
    except:
        return {"error": "Texture map not generated yet"}, 500

    return send_file(img_bytes, mimetype='image/png')

if __name__ == "__main__":
    chunk_storage = ChunkStorage(api_server=API_SERVER)
    app.run(host="0.0.0.0", port=8091)
