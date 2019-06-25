import datetime
from flask import Flask, render_template
from flask_admin import Admin
from flask_simplelogin import SimpleLogin
from Library.FaceHandler import FaceHandler
from Library.CameraHandler import CameraHandler
from Library.SettingsHandler import SettingsHandler
from Library.DatabaseHandler import DatabaseHandler
import logging
import cv2
from pathlib import Path

from config import Config
from bcrypt import hashpw, gensalt, checkpw
import sqlite3 as sql


class FHApp(Flask):
    fh: FaceHandler
    ch: CameraHandler
    sh: SettingsHandler
    dh: DatabaseHandler


app: FHApp


# cache_buster_config = {'extensions': ['.png', '.css', '.csv'], 'hash_size': 10}
# cache_buster = CacheBuster(config=cache_buster_config)

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
    logging.info("Password changed")
    return pwd


def validate_login(login_form):
    """ used to override simple_login's loginchecker, thus allowing the use of encrypted passwords """
    correct_hash = get_hashed_login_passwd()
    candidate_password = login_form['password'].encode('utf-8')
    if checkpw(candidate_password, correct_hash):
        return True
    return False


def on_known_enters(persons):
    """ Custom behaviour for the facehandler's callback method of the same name """
    for person in persons:
        logging.info("Entered: {}".format(person.name))
        app.fh.mqtt.publish(
            app.fh.notification_settings["topic"],
            "[recognEYEz][ARRIVED][date: {}]: {}".format(datetime.datetime.now().strftime(app.config["TIME_FORMAT"]), person.name)
        )
        app.dh.log_event("[ARRIVED]: {}".format(person.name))
        logging.info("[ARRIVED]: {}".format(person.name))


def on_known_leaves(persons):
    """ Custom behaviour for the facehandler's callback method of the same name """
    for person in persons:
        app.fh.mqtt.publish(
            app.fh.notification_settings["topic"],
            "[recognEYEz][LEFT][date: {}]: {}".format(datetime.datetime.now().strftime(app.config["TIME_FORMAT"]), person.name)
        )
        app.dh.log_event("[LEFT]: {}".format(person.name))
        logging.info("[LEFT]: {}".format(person.name))


def init_app(app, db_loc="facerecognition.db"):
    """ Initializes handlers instance """
    if not app.dh:
        app.dh = DatabaseHandler(app, db_loc)
    if not app.sh:
        app.sh = SettingsHandler(app)
    if not app.ch:
        app.ch = CameraHandler(app)
    if not app.fh:
        app.fh = FaceHandler(app,
                             db_loc,
                             cascade_xml="haarcascade_frontalface_default.xml",
                             img_root=Path("Static").joinpath("dnn")
                             )
        app.fh.running_since = datetime.datetime.now()
        # override the callback methods
        app.fh.on_known_face_enters = on_known_enters
        app.fh.on_known_face_leaves = on_known_leaves

def login():
    """ needed for simple login to render the proper template """
    return render_template("login.html")

# parameter is the config Class from config.py
def create_app(config_class=Config):
    global app
    app = FHApp(__name__, static_url_path='', static_folder='./Static', template_folder='./Templates')
    app.config.from_object(config_class)
    # t = threading.Thread(target=init_fh, args=(app,))
    # t.start()
    init_app(app)

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
    app.admin = Admin(app, name='recogneyez', template_mode='bootstrap3')
    app.ticker = 0

    SimpleLogin(app, login_checker=validate_login)
    # cache_buster.register_cache_buster(app)
    app.force_rescan = False

    app.preview_image = cv2.imread("Static/empty_pic.png")

    app.camera_thread = None

    # app.ch.camera_start_processing()

    return app
