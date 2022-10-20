from flask import Flask, render_template, url_for, request, redirect, abort, session, make_response
import requests
import base64
import json
import secrets
from requests_toolbelt.utils import dump
from urllib.parse import urlencode
import pymongo
from flask_cors import CORS
from datetime import datetime, timedelta
import hashlib
from googletrans import Translator

app = Flask(__name__)
CORS(app)
translator = Translator()

serverIP="http://127.0.0.1:5000"

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["spotify-db"]
mycol = mydb["user"]

# high level function:
def make_token():
    """
    Creates a cryptographically-secure, URL-safe string
    """
    return secrets.token_urlsafe(16)  

def generate_digest(plaintext):
    byte_data = plaintext.encode()
    d = hashlib.sha256(byte_data)
    hash = d.digest()
    return hash.hex()

def mongo_user(usr, pw, client_id, client_secret):
    myquery = {"user": usr}
    mydoc = mycol.find_one(myquery)
    if mydoc != None:
         if (mydoc["password"] != pw):
             return 1
    ins = {
        "user": usr,
        "password": pw,
        "client_id": client_id,
        "client_secret": client_secret
    }
    mycol.update_one(myquery, {"$set": ins}, upsert=True)
    return 0

def encode_decode(id, secret):
    # message encode
    message = f"{id}:{secret}"
    messageBytes = message.encode('ascii')
    base64Bytes = base64.b64encode(messageBytes)
    base64Message = base64Bytes.decode('ascii')
    return base64Message

def json_create(ins):
    data = {}
    song_title = ins["item"]["name"]
    artist_arr = ins["item"]["artists"][::]
    artists = ""
    list_artists = []
    
    for x in artist_arr:
        artist = x["name"]
        try:
            artist.encode('ascii')
        except UnicodeEncodeError :
            y = translator.translate(artist, "en")
            artist = y.text
            artist = artist.encode('ascii', "ignore")
            artist = artist.decode()
        list_artists.append(artist)   
    
    for z in list_artists:
        temp = z
        if (len(temp) > 60):
            temp = z[:6] + "..."
        artists += temp
        if (list_artists.index(z) == 0) and (len(list_artists) == 2):
            artists += " and "
        if len(artist_arr) > 2:
            artists += " etc"
            break

    try:
        song_title.encode('ascii')
    except UnicodeEncodeError :
        x = translator.translate(song_title, "en")
        song_title = x.text
        song_title = song_title.encode('ascii', "ignore")
        song_title = song_title.decode()
    data["song_title"] = song_title
    data["artist_string"] = artists
    data["artist_full"] = list_artists
    data["device_name"] = ins["device"]["name"]
    data["status"] = ins["is_playing"]
    data["timer"] = int(ins["item"]["duration_ms"]) - int(ins["progress_ms"])
    print(data)
    return data


# flask GET/POST functions
@app.route("/")
def hello_world():
    return render_template("home.html")

@app.route('/admin', methods = ['GET', 'POST'])
def admin():
    if request.method == 'POST':        
        # fetch client id & secret
        user = request.form['uid']
        passw = generate_digest(request.form['pass'])
        clientId = request.form['id']
        clientSecret = request.form['secret']
        r = mongo_user(user, passw, clientId, clientSecret)
        if r == 1:
            return "wrong pass"
        state = make_token()
        res = make_response(redirect("/success"))  
        res.set_cookie('state', state)
        session_ins = { "$set": { "state": state} }
        myquery = {"user": user}
        mycol.update_one(myquery, session_ins, upsert=True)
        return res
    else:
        return render_template("admin.html")

@app.route('/test-endpoint')
def test():
    print(translator.detect("이 문장은 한글로 쓰여졌습니다"))
    print(translator.detect("この文章は日本語で書かれました。"))
    return "test"

@app.route('/success')
def success():
    return render_template("success.html")
        
@app.route('/authorize')
def authorize():
    if 'state' not in request.cookies:
        print("state not in session")
        return redirect(url_for('admin'))
    state = request.cookies.get('state')
    myquery = {"state": state}
    mydoc = mycol.find_one(myquery)
    if mydoc == None:
        print("state mismatch")
        return redirect(url_for('admin'))
    auth_headers = {
        "client_id": mydoc["client_id"],
        "response_type": "code",
        "redirect_uri": "http://127.0.0.1:5000/callback",
        "scope": "user-library-read user-read-playback-state user-read-currently-playing",
        "state": state
    }
    url = "https://accounts.spotify.com/authorize?" + urlencode(auth_headers)
    res = make_response(redirect(url))  
    res.set_cookie('state', state)
    return res

@app.route('/callback')
def callback():
    #### cookies does not work somehow, ignore

    # if 'state' not in request.cookies:
    #     print("state not in session")
    #     return redirect(url_for('admin'))
    # if request.cookies.get('state') != request.args.get('state'):
    #     print("state not in session")
    #     return "state mismatch"

    # curl -d client_id=$CLIENT_ID -d client_secret=$CLIENT_SECRET \
    #  -d grant_type=authorization_code -d code=$CODE -d redirect_uri=$REDIRECT_URI \
    #  https://accounts.spotify.com/api/token
    myquery = {"state": request.args.get('state')}
    mydoc = mycol.find_one(myquery)
    url = "https://accounts.spotify.com/api/token"
    payload={
        "client_id": mydoc["client_id"],
        "client_secret": mydoc["client_secret"],
        "grant_type":"authorization_code",
        "code": request.args.get('code'),
        "redirect_uri": "http://127.0.0.1:5000/callback"
    }   

    expiry = datetime.now() + timedelta(hours=1)
    r = requests.post(url, data=payload)

    str_expiry = expiry.strftime("%m/%d/%Y, %H:%M:%S")

    result = {
        "access_token": r.json()["access_token"],
        "refresh_token": r.json()["refresh_token"],
        "token_expire": str_expiry
    }
    mycol.update_one(myquery, {"$set": result}, upsert=True)
    res = make_response(result)  
    res.set_cookie('state', request.args.get('state'))
    return res

@app.post('/refresh')
def refresh():
    # curl -H "Authorization: Basic <base64 encoded client_id:client_secret>"
    #  -d grant_type=refresh_token -d refresh_token=$ref_token 
    #  https://accounts.spotify.com/api/token

    url = "https://accounts.spotify.com/api/token"

    myquery = {"user": request.form['uid']}
    mydoc = mycol.find_one(myquery)

    if mydoc == None:
        return abort(404)
    try:
        id = mydoc["client_id"]
        secret = mydoc["client_secret"]
        ref_token = mydoc["refresh_token"]
    except KeyError:
        return redirect(url_for('authorize'))
    
    base64Message = encode_decode(id,secret)

    # wrap headers
    head = {}
    head['Authorization'] = f"Basic {base64Message}"

    payload={
        "grant_type":"refresh_token",
        "refresh_token": ref_token
    }
    
    expiry = datetime.now() + timedelta(hours=1)
    r = requests.post(url, headers=head,data=payload)
    str_expiry = expiry.strftime("%m/%d/%Y, %H:%M:%S")
    result = {
        "access_token": r.json()["access_token"],
        "token_expire": str_expiry
    }
    mycol.update_one(myquery, {"$set": result}, upsert=True)
    res = make_response(result)
    return res

@app.post("/get")
def get_track():
    myquery = {"user": request.form['uid']}
    mydoc = mycol.find_one(myquery)

    if mydoc == None:
        return abort(404)
    try:
        expiry = datetime.strptime(mydoc["token_expire"], "%m/%d/%Y, %H:%M:%S")
    except KeyError:
        return redirect(url_for('authorize'))    

    if datetime.now() > expiry:
        payload={
            "uid": request.form['uid']
        }   
        r = requests.post(serverIP + "/refresh", data=payload)
        mydoc = mycol.find_one(myquery)
    token = mydoc["access_token"]

    url = 'https://api.spotify.com/v1/me/player'
    
    # custom header
    params={
        "Accept":"application/json",
        "Content-Type":"application/json",
        "Authorization":"Bearer " + token
    }
    
    resp = requests.get(url=url, headers=params)
    print(resp.status_code)
    # print(dump.dump_all(resp))
    data = {}
    try:
        #print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        data = json_create(resp.json())
        data["api_response"] = resp.status_code
        return data
    except:
        data["api_response"] = resp.status_code
        return data

if __name__ == "__main__":
    app.run(host="0.0.0.0")