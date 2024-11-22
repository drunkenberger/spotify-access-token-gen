import os
import requests
from flask import Flask, request, redirect, session, url_for, render_template
from urllib.parse import urlencode

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Use environment variable in production

# Spotify API constants
SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"

# Initialize as None, will be set through the form
CLIENT_ID = None
CLIENT_SECRET = None
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:8888/callback')

def get_spotify_authorize_url(client_id, redirect_uri, scope):
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
    }
    return f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(params)}"

def get_spotify_access_token(client_id, client_secret, redirect_uri, code):
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    response.raise_for_status()
    return response.json()

def refresh_spotify_access_token(client_id, client_secret, refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    response.raise_for_status()
    return response.json()

def get_user_id(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(SPOTIFY_ME_URL, headers=headers)
    response.raise_for_status()
    return response.json()["id"]

@app.route('/', methods=['GET'])
def index():
    return render_template('login.html')

@app.route('/submit-credentials', methods=['POST'])
def submit_credentials():
    global CLIENT_ID, CLIENT_SECRET
    CLIENT_ID = request.form['client_id']
    CLIENT_SECRET = request.form['client_secret']
    auth_url = get_spotify_authorize_url(CLIENT_ID, REDIRECT_URI, "playlist-modify-public user-read-private")
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    tokens = get_spotify_access_token(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, code)
    session['access_token'] = tokens["access_token"]
    session['refresh_token'] = tokens["refresh_token"]
    user_id = get_user_id(session['access_token'])
    session['user_id'] = user_id
    return render_template('result.html',
                         user_id=user_id,
                         access_token=session['access_token'],
                         refresh_token=session['refresh_token'])

@app.route('/refresh')
def refresh():
    tokens = refresh_spotify_access_token(CLIENT_ID, CLIENT_SECRET, session['refresh_token'])
    session['access_token'] = tokens["access_token"]
    return render_template('result.html',
                         user_id=session['user_id'],
                         access_token=session['access_token'],
                         refresh_token=session['refresh_token'])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8888))
    app.run(host='0.0.0.0', port=port)
