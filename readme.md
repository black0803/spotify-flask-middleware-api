
# Flask-based Middleware REST API for Spotify
 > A piece from two component (esp+hd44780, flask) project   
 >
 > Disclaimer: It's my first backend API I ever create, my background is Computer Engineering (Degree) and Cloud Infrastructure Engineer (Work) so there might be some bad practice that I ended up doing. If you saw this and notice some parts that could've been implemented better, please kindly notify me, I'm open for advices.
 
 ### Github Repo URL for this project:
 - [Python Flask Middleware](https://github.com/black0803/spotify-flask-middleware-api "Middleware API for Spotify Based on Python Flask")
 - [ESP+hd44780 Frontend](https://github.com/black0803/spotify-esp-display "Front end tier of the spotify display project using ESP and hd44780 16x2 LCD")

 ### Application Architecture
 ![Application Architecture Diagram](https://github.com/black0803/spotify-flask-middleware-api/blob/main/img/app-architecture-design.png?raw=true)  
 The application is split into 3 roughly three components, which will be stated as frontend, middleware, and (real) backend. Frontend is covered by the ESP and hd44780 LCD, while the middleware is the whole flask deployment together with mongodb as the database, and spotify (+google translate, which is a bonus actually) as its true backend. This python application provides you an endpoint to hit spotify API using custom identities, with simplified output as well to make parsing data in ESP easier.

 ![Application Instructions Diagram](https://github.com/black0803/spotify-flask-middleware-api/blob/main/img/app-flow-design.png?raw=true)  
 The expected flow of the application when you are using ESP32 to display is as follow:  
 - ESP sends a HTTP POST Request to /get, with "Content-Type=application/x-www-form-urlencoded" and payload "uid=<username>"
   > curl representation:
   > ``curl -H "Content-Type=application/x-www-form-urlencoded" -d uid=nobita http://192.168.1.225:5000/get``
 - Python Flask fetch access token that are saved on MongoDB
 - Using the access token from mongodb, Python hit POST message to https://api.spotify.com/v1/me/player, and wait for the json file sent by spotify API to be processed for Flask's response
 - Python flask parse the received json, and send only the necessary part for the ESP to use.
 - ESP receive the response from Python Flask, and then display the result to the LCD.

 ### How to use:
 - If you just want to run the web server, you can just do as follow:
   - Copy ``.env`` file from ``.env_copy``, and adjust the variables inside (``$MONGO_HOST`` and ``$FLASK_SERVER``) to suit your need.
   - Run ``python -m venv <venv>`` to initialize venv for your python script folder
   - Run ``<venv>/bin/activate`` to start your console in virtual environment
   - Install the libraries using ``pip install -r requirements.txt``
   - Run ``gunicorn --workers <worker_node> --bind <ip:port> wsgi:app``
     - ``--bind 0.0.0.0`` to make the server run in all interface (internet facing if you have public ip attached). For home setup, you can access the flask server via your local interface with this (192.168.x.x:8000). Not specifying port number means it automatically run on port 8000
     - ``--bind 127.0.0.1`` if you don't want to expose your flask server. This is one of the option if you are using reverse proxy such as nginx.
  - For nginx + gunicorn deployment in linux-based server, you can look at the provided nginx-conf and gunicorn.service .
    - Adjust your ``gunicorn.service`` file, copy to ``/etc/systemd/system/``
    - Run ``sudo systemctl start gunicorn.service && sudo systemctl enable gunicorn.service``
      - If you made mistake in adjusting ``gunicorn.service``, you can edit the file again using text editor BUT you must perform ``sudo systemctl daemon-reload`` before running the restart command.
    - Install nginx, put ``server.conf`` to ``/etc/nginx/conf.d/``
    - Comment the server block on ``nginx.conf``. Test using ``sudo nginx -t`` to check if your nginx configuration file is already valid.
    - Run ``sudo systemctl restart nginx``

 ### Provided Endpoint:
  - GET / : root/home page, contains forms to test some of the POST endpoints
  - GET /admin : login + registration page, flow to be improved but _temporarily this works_.
  - POST /admin : approval for the login/registration
  - GET /success : redirect endpoint for successful command
  - GET /authorize : endpoint to redirect to spotify authorization
  - GET /callback : necessary endpoint required by spotify
  - POST /refresh : endpoint to refresh token (auth token expire every hour). Can be tested via root endpoint (/).
  - POST /get : endpoint to fetch currently playing songs and some other data. Can be tested via root endpoint (/).

 ### Live Server:
 You can see a demo for this server in http://www.spotify.black0803.my.id, I used gunicorn + nginx on a VPS with this spec:
 - 1 CPU
 - 512 MB RAM
 - 10GB Storage
 - Centos 7
 - rumahweb.com hosting, hosted on AZ Technovillage Bekasi.
 - domainesia.com domain hosting  
 
 As expected, server does not perform all that well because of the limited VPS capability. I have plans on moving this to AWS using t3.micro free tier for one year, but that come after my VPS subscription finished.

 To test the endpoint, head to my server and insert ``nobita`` to GetSong API Test Form. You can see my currently-playing song in the JSON output.

 DISCLAIMER: Data is saved on mongodb atlas server. I personally just leave it live and does not observe the DB. If you are trying to use the publicly hosted mongodb, please do with your own risk. I as the app developer won't be responsible for the data you inserted, since this is actually just meant for my home project.

 ### (Planned) Future Improvements:
 - Showing the song duration and current progress of the song. I haven't consider how things will be shown on the LCD as currently it already occupies the whole 16x2 slot as is. However, it is possible to implement this and I will try to do it as well.
 - Dockerize app.

 ### Known Issues:
 - hd44780 LCD is a very small LCD with limitations that restricts the outputted text to only ASCII letters. This means that non-ASCII based letters (arabic, korean, japanese, which utilizes unicode[UTF-8 or UTF-16]) makes it undisplayable to the screen. To circumvent this, I actually applied a Google Translate library provided as a method to pass the load of translating the title and artist name. This straightforward approach means some names do not get translated properly, which makes it sort of bad. If you have any recommendation on what to use to merely transcribe the letters into plaintext, that will be helpful.