import datetime
from flask import Flask, request, render_template, redirect
from flask_admin import Admin
import flask_simplelogin as simplog
import threading
from FaceHandler import FaceHandler

#from flask_cache_buster import CacheBuster

from config import Config
from bcrypt import hashpw, gensalt, checkpw
import sqlite3 as sql


most_recent_scan_date = None



#cache_buster_config = {'extensions': ['.png', '.css', '.csv'], 'hash_size': 10}
#cache_buster = CacheBuster(config=cache_buster_config)


def get_hashed_login_passwd():
    """returns the hash of the current password stored in the database"""
    connection = sql.connect(app.config["PAGE_DATABASE"])
    cursor = connection.cursor()
    cursor.execute('SELECT password FROM users WHERE name="admin"')
    pwd_hash = cursor.fetchone()
    connection.close()
    return pwd_hash[0]


def set_hashed_login_passwd(pwd):
    """ updates the password hash in the database """
    pwd = hashpw(pwd.encode('utf-8'), gensalt())
    connection = sql.connect(app.config["PAGE_DATABASE"])
    cursor = connection.cursor()
    cursor.execute('UPDATE users SET password = ? WHERE name="admin"', (pwd,))
    connection.commit()
    connection.close()
    print("[INFO] Password changed")
    return pwd


def validate_login(login_form):
    """ used to override simple_login's loginchecker, thus allowing the use of encrypted passwords """
    correct_hash = get_hashed_login_passwd()
    candidate_password = login_form['password'].encode('utf-8')
    if checkpw(candidate_password, correct_hash):
        return True
    return False


def on_known_enters(persons):
    """ Costume behaviour for the facehandler's callback method of the same name """
    name = str(persons.keys())[11:-2]
    print("Entered: " + name)
    app.fh.mqtt.publish(
        app.fh.notification_settings["topic"],
        "[T-Eye][ARRIVED][date: " + datetime.datetime.now().strftime(app.config["TIME_FORMAT"]) + "]: " + name
    )
    app.fh.db.log("[ARRIVED]: %s" % name)


def on_known_leaves(persons):
    """ Costume behaviour for the facehandler's callback method of the same name """
    name = str(persons.keys())[11:-2]
    app.fh.mqtt.publish(
        app.fh.notification_settings["topic"],
        "[T-Eye][LEFT][date: " + datetime.datetime.now().strftime(app.config["TIME_FORMAT"]) + "]: " + name
    )
    app.fh.db.log("[LEFT]: %s" % name)


def init_fh(app):
    """ Initializes a face handler instance """
    if not app.fh:
        app.fh = FaceHandler(
            cascade_xml="haarcascade_frontalface_default.xml",
            img_root="Static/dnn_data"
        )
        # start_cam()
        app.fh.running_since = datetime.datetime.now()
        # override the callback methods
        app.fh.on_known_face_enters = on_known_enters
        app.fh.on_known_face_leaves = on_known_leaves


def log(log_text):
    date = datetime.datetime.now().strftime(app.TIME_FORMAT)
    with open("log.txt", "a+") as f:
        f.write("[" + date + "] " + str(log_text) + " <br>\n")


def who_is_there(use_dnn=False):
    """
    returns a list of currently visible people
    """
    if use_dnn:
        visible_p = app.fh.process_next_frame(True)
    else:
        visible_p = app.fh.process_next_frame()
    print("present")
    for p in visible_p:
        print(p.name)
    return visible_p


def login():
    """ needed for simple login to render the proper template """
    return render_template("login.html")


def create_app(config_class=Config):
    global app
    app = Flask(__name__, static_url_path='', static_folder = './Static', template_folder='./Templates')
    app.config.from_object(config_class)
    app.fh = None
    t = threading.Thread(target=init_fh, args=(app,))
    t.start()

    # import the blueprints
    from blueprints.live_view.routes import live_view
    app.register_blueprint(live_view)

    from blueprints.config_page.routes import config_page
    app.register_blueprint(config_page)

    from blueprints.persons_database.routes import persons_database
    app.register_blueprint(persons_database)

    from blueprints.person_edit.routes import person_edit
    app.register_blueprint(person_edit)

    from blueprints.actions.routes import actions
    app.register_blueprint(actions)

    from blueprints.errors.handlers import errors
    app.register_blueprint(errors)

    app.dnn_iter = 0
    app.present = []
    app.threads = []
    app.admin = Admin(app, name='microblog', template_mode='bootstrap3')

    simplog.SimpleLogin(app, login_checker=validate_login)
#    cache_buster.register_cache_buster(app)
    app.force_rescan = False
    return app

