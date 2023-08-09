from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
import os
import base64
from requests import post, get
import json
from urllib.parse import urlencode
from flask import jsonify

app = Flask(__name__)
app.secret_key = "Nadeem@04"
load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

spotify_user_id = None


@app.route("/spotify_login")
def spotify_login():
    scope = "user-read-private user-read-email user-top-read"  
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

    if result.status_code == 200:
        try:
            token_data = json.loads(result.content)
            return token_data
        except json.JSONDecodeError as e:
            print("Error decoding JSON response:", e)
    else:
        print("Error: Unable to get access token from Spotify. Status code:", result.status_code)
        print("Response content:", result.content)
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

    playlist_tracks = add_tracks_from_playlists(playlists, token)
    for track in json_result:
        track["in_playlist"] = find_track_in_playlists(track, playlist_tracks)
  
    return json_result


def get_user_playlists(token):
    url = "https://api.spotify.com/v1/users/{spotify_user_id}/playlists"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    json_result = json.loads(result.content)
    playlists = json_result.get("items", []) 
    # print("User Playlists Response:", json_result)
    return playlists

def add_tracks_from_playlists(playlists, token):
    tracks = [dict() for x in range(len(playlists))]
    for i in range(len(playlists)):
        playlist_tracks = get_playlist_tracks(playlists[i]["id"], playlists[i]["tracks"]["total"], token)
        tracks[i]["name"] = playlists[i]["name"]
        track_ids = []
        for track in playlist_tracks:
            track_ids.append(track["track"]["id"])
        tracks[i]["tracks"] = track_ids
    return tracks
        

def find_track_in_playlists(track, playlists):
    for playlist in playlists:
        for playlist_track in playlist["tracks"]:
            if track['id'] == playlist_track:
                return playlist["name"]
    return None




def get_playlist_tracks(playlist_id, playlist_length, token):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = get_auth_header(token)
    fields = "fields=items.track.id"
    tracks = []
    
    n = 0;
    while n < playlist_length:
        result = get(url + "?" + fields + "&" + "offset=" + str(n), headers=headers)
        json_result = json.loads(result.content)
        tracks.extend(json_result.get("items", []))
        n+=100;

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
        if user_info and "id" in user_info:
            spotify_user_id = user_info["id"]

    return render_template("index.html", spotify_username=spotify_username, result=result)


def get_user_info(token):
    url = "https://api.spotify.com/v1/me"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    if result.status_code == 200:
        return json.loads(result.content)
    return None


@app.route("/get_listening_habits")
def get_listening_habits():
    token = session.get("spotify_access_token")
    if token:
        top_genres_data = get_top_genres(token)
        if top_genres_data:
            return render_template("listening_habits.html", top_genres_data=top_genres_data)
        else:
            return "Error: Unable to retrieve top genres data."
    else:
        return redirect(url_for("spotify_login"))



def get_top_genres(token):
    url = "https://api.spotify.com/v1/me/top/artists"
    headers = get_auth_header(token)
    params = {
        "time_range": "medium_term",  
        "limit": 10,  
    }
    result = get(url, headers=headers, params=params)

    if result.status_code == 200:
        try:
            json_result = result.json()
            top_genres_data = [{"genre": artist["genres"], "count": artist["popularity"]} for artist in json_result["items"]]
            return top_genres_data
        except json.JSONDecodeError as e:
            print("Error decoding JSON response:", e)
    else:
        print("Error: Unable to get top genres. Status code:", result.status_code)
        print("Response content:", result.content)

    return None




@app.route("/get_top_artists")
def get_top_artists(token, genre):
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q=genre:{genre}&type=artist&limit=10"  

    query_url = url + query
    result = get(query_url, headers=headers)
    json_result = json.loads(result.content)["artists"]["items"]
    return json_result



if __name__ == "__main__":
    app.run(debug=True)