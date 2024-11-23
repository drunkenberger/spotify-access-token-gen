import requests
from flask import Flask, request, redirect, session, url_for, render_template
from urllib.parse import urlencode
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate a random secret key
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True if using HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800  # 30 minutes
)

# Spotify API constants
SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"

# Initialize as None, will be set through the form
CLIENT_ID = None
CLIENT_SECRET = None
REDIRECT_URI = 'http://localhost:8888/callback'

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
    
    print("\nAttempting to get access token with:")
    print(f"Client ID: {client_id[:5]}..." if client_id else "None")
    print(f"Client Secret: {'*' * 5}..." if client_secret else "None")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Code length: {len(code) if code else 'None'}")
    
    try:
        response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
        print(f"\nResponse status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text}\n")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP Error occurred: {e}")
        print(f"Response content: {e.response.text}")
        raise

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
    # Store credentials in session
    session.clear()  # Clear any existing session data
    session['client_id'] = request.form['client_id'].strip()
    session['client_secret'] = request.form['client_secret'].strip()
    
    print("Credentials stored in session:")
    print(f"Client ID: {session['client_id'][:5]}...")
    print(f"Client Secret: {'*' * 5}...")
    
    auth_url = get_spotify_authorize_url(
        session['client_id'], 
        REDIRECT_URI, 
        "playlist-modify-public user-read-private"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    print("\nCallback received. Session contents:")
    print(f"client_id in session: {'Yes' if 'client_id' in session else 'No'}")
    print(f"client_secret in session: {'Yes' if 'client_secret' in session else 'No'}")
    
    if 'client_id' not in session or 'client_secret' not in session:
        return """
            Error: Client credentials not found. Please start over. 
            <br><br>
            <a href="/">Return to login page</a>
        """, 400
    
    code = request.args.get('code')
    if not code:
        return "Error: No authorization code received from Spotify", 400
    
    try:
        tokens = get_spotify_access_token(
            session['client_id'],
            session['client_secret'],
            REDIRECT_URI,
            code
        )
        session['access_token'] = tokens["access_token"]
        session['refresh_token'] = tokens["refresh_token"]
        user_id = get_user_id(session['access_token'])
        session['user_id'] = user_id
        return render_template('result.html',
                             user_id=user_id,
                             access_token=session['access_token'],
                             refresh_token=session['refresh_token'])
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {str(e)}")
        print(f"Response content: {e.response.text}")
        return f"Error getting access token: {str(e)}", 400
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return f"Unexpected error: {str(e)}", 500

@app.route('/refresh')
def refresh():
    if 'client_id' not in session or 'client_secret' not in session:
        return "Error: Client credentials not found. Please start over.", 400
    
    try:
        tokens = refresh_spotify_access_token(
            session['client_id'],
            session['client_secret'],
            session['refresh_token']
        )
        session['access_token'] = tokens["access_token"]
        return render_template('result.html',
                             user_id=session['user_id'],
                             access_token=session['access_token'],
                             refresh_token=session['refresh_token'])
    except Exception as e:
        return f"Error refreshing token: {str(e)}", 400

@app.route('/test-session')
def test_session():
    return {
        'client_id_present': 'client_id' in session,
        'client_secret_present': 'client_secret' in session,
        'session_data': {k: v[:5] + '...' if k in ['client_id', 'client_secret'] else v 
                        for k, v in session.items()}
    }

if __name__ == '__main__':
    app.run(host='localhost', port=8888, debug=True)
