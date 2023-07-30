from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
import os
import base64
from requests import post, get
import json
from urllib.parse import urlencode




app = Flask(__name__)
app.secret_key = "Nadeem@04"
load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

@app.route("/spotify_login")
def spotify_login():
    scope = "user-read-private user-read-email"  
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": "http://localhost:5000/spotify_callback",
        "scope": scope,
    }
    query_string = urlencode(params)
    auth_url = "https://accounts.spotify.com/authorize?" + query_string
    return redirect(auth_url)

@app.route("/spotify_callback")
def spotify_callback():
    auth_code = request.args.get("code")
    if auth_code:
        token_data = get_access_token(auth_code)
        if token_data and "access_token" in token_data:
            session["spotify_access_token"] = token_data["access_token"]
            return redirect(url_for("index"))
        else:
            return "Error: Unable to get access token from Spotify."
    else:
        return "Error: No auth code received from Spotify."

def get_access_token(auth_code):
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": "http://localhost:5000/spotify_callback",  
        "client_id": client_id,
        "client_secret": client_secret,
    }
    result = post(url, data=data)
    print("Response status code:", result.status_code)
    print("Response content:", result.content)
    
    if result.status_code == 200:
        return json.loads(result.content)
    return None


def get_auth_header():
    token = session.get("spotify_access_token")
    if token:
        return {"Authorization": "Bearer " + token}
    return {}

def get_token():
    auth_string = client_id + ":" + client_secret
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}
    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result["access_token"]
    return token


def get_auth_header(token):
    return {"Authorization": "Bearer " + token}


def search_for_artist(token, artist_name):
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q={artist_name}&type=artist&limit=1"

    query_url = url + query
    result = get(query_url, headers=headers)
    json_result = json.loads(result.content)["artists"]["items"]
    if len(json_result) == 0:
        return None

    return json_result[0]



def get_songs_by_artist(token, artist_id):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?country=CA"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    json_result = json.loads(result.content)["tracks"]

    playlists = get_user_playlists(token)

    for track in json_result:
        track["in_playlist"] = find_track_in_playlists(track, playlists)

    return json_result


def get_user_playlists(token):
    url = "https://api.spotify.com/v1/me/playlists"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    json_result = json.loads(result.content)
    playlists = json_result.get("items", []) 
    print("User Playlists Response:", json_result)
    return playlists


def find_track_in_playlists(track, playlists):
    track_id = track["id"]
    for playlist in playlists:
        playlist_tracks = get_playlist_tracks(playlist["id"])
        for playlist_track in playlist_tracks:
            if "track" in playlist_track and playlist_track["track"]["id"] == track_id:
                return playlist["name"]
    return None



def get_playlist_tracks(playlist_id):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = get_auth_header()
    tracks = []

    while url:
        result = get(url, headers=headers)
        json_result = json.loads(result.content)
        tracks.extend(json_result.get("items", []))
        url = json_result.get("next")

    return tracks







@app.route("/", methods=["GET", "POST"])
def index():
    result = None  
    if request.method == "POST":
        artist_name = request.form.get("artist_name")
        token = get_token()
        result = search_for_artist(token, artist_name)

        if result:
            artist_id = result["id"]
            songs = get_songs_by_artist(token, artist_id)
            return render_template("results.html", artist=result, songs=songs)
        else:
            return render_template(
                "index.html", error_message="No artist found. Please try again."
            )

    spotify_username = None
    token = session.get("spotify_access_token")
    if token:
        user_info = get_user_info(token)
        if user_info and "display_name" in user_info:
            spotify_username = user_info["display_name"]

    return render_template("index.html", spotify_username=spotify_username, result=result)


def get_user_info(token):
    url = "https://api.spotify.com/v1/me"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    if result.status_code == 200:
        return json.loads(result.content)
    return None


if __name__ == "__main__":
    app.run(debug=True)
