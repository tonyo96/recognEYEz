import sqlite3 as sql
from datetime import datetime
import logging
from peewee import *
from typing import List
import logging
from pathlib import Path
from imutils import paths

db = SqliteDatabase('recogneyez.db')


class DBModel(Model):
    class Meta:
        database = db


class Person(DBModel):
    name = TextField(unique=True)
    preference = TextField(null=True)
    group = IntegerField(null=True)
    first_seen = DateTimeField(null=True)
    last_seen = DateTimeField(null=True)
    thumbnail = DeferredForeignKey(
        'Image', deferrable='INITIALLY DEFERRED', on_delete='SET_NULL', null=True)
    unknown = BooleanField(default=True)

    def add_image(self, image_name: str, set_as_thumbnail: bool=False):
        image = Image()
        image.person = self
        image.save()

        if set_as_thumbnail:
            self.set_thumbnail(image)

        logging.info("{} image was added for the person {}".format(
            image_name, self.name))

    def set_thumbnail(self, thumbnail: Image):
        self.thumbnail = thumbnail
        self.save()


class Encoding(DBModel):
    encoding = BlobField(null=True)
    person = ForeignKeyField(Person, backref='encodings', on_delete='CASCADE')


class UserEvent(DBModel):
    datetime = DateTimeField()
    event = TextField()


class Image(DBModel):
    name = TextField(unique=True)
    Person = ForeignKeyField(Person, backref='images', on_delete='CASCADE')


class DatabaseHandler:
    TIME_FORMAT = "%Y.%m.%d. %H:%M:%S"

    def __init__(self, db_location):
        self.db_loc = db_location
        self.active_connection = False
        db.connect()
        db.create_tables([UserEvent, Encoding, Person])

    def open_and_get_cursor(self):
        """ Opens and stores connection for the db + returns a cursor object"""
        self.active_connection = sql.connect(self.db_loc)
        return self.active_connection.cursor()

    def commit_and_close_connection(self):
        """Commits the current changes and closes the connection"""
        self.active_connection.commit()
        self.active_connection.close()
        self.active_connection = False
        return True

    def get_all_events(self) -> List:
        return UserEvent.select()

    def log_event(self, text: str):
        new_event = UserEvent.create(datetime=datetime.now(), event=text)
        new_event.save()

    def remove_name(self, name: str) -> bool:
        """Removes the given name from both tables (removes all the encodings)"""
        logging.info("Removing {}".format(name))
        return Person.delete().where(Person.name == name).execute() > 0

    def remove_unknown_name(self, name: str) -> bool:
        """Removes the given name from both tables (removes all the encodings)"""
        return self.remove_name(name)

    def merge_unknown(self, merge_from_name: str, merge_to_name: str) -> bool:
        """"""
        logging.info("Merging {} with {}".format(
            merge_from_name, merge_to_name))
        merge_to = Person.get(Person.name == merge_to_name)
        merge_from = Person.get(Person.name == merge_from_name)
        merge_from.encodings.update(person=merge_to).execute()
        return merge_from.delete().execute() > 0

    def create_new_from_unknown(self, name: str, folder: str) -> bool:
        """"""
        Person.update(unknown=False).where(Person.name == name).execute()
        logging.info("Created new person {}".format(name))

    def get_persons(self) -> List[Person]:
        """
        Returns a list containing a list of attributes, which represents persons
            0 - id, 1 - name, 2 - pref, 6 - thumbnail
        Can return a dict:
            key: id, name, pref, thumbnail
        don't use ID in code
        """
        logging.info("Getting all persons")
        persons = Person.select()
        encodings = Encoding.select()
        images = images.select()
        # prefetch is needed to eagerly load related subqueries
        # this avoids the potential N+1 query problem in iterations in Jinja for example
        return prefetch(persons, encodings, images)

    def get_known_persons(self) -> List[Person]:
        logging.info("Getting known persons")
        persons = Person.select().where(Person.unknown == False)
        encodings = Encoding.select()
        images = images.select()
        return prefetch(persons, encodings, images)

    def get_unknown_persons(self) -> List[Person]:
        """
        Returns a list containing a list of attributes, which represents persons
            0 - id, 1 - name
        Can return a dict:
            key: id, name, date
        don't use ID in code
        """
        logging.info("Getting unknown persons")
        persons = Person.select().where(Person.unknown == True)
        encodings = Encoding.select()
        images = images.select()
        return prefetch(persons, encodings, images)

    def update_person_data(self, old_name: str, new_name: str = None, new_pref: str = None) -> Person:
        """
        Updates recors in persons table
        Uses the old name to find the record
        Returns the new person
        """
        if not new_name:
            new_name = old_name
        if new_pref:
            Person.update(name=new_name, preference=new_pref).where(
                Person.name == old_name).execute()
        else:
            Person.update(name=new_name).where(
                Person.name == old_name).execute()
        logging.info("Updated person {}".format(new_name))
        return Person.get(Person.name == new_name)

    def update_face_recognition_settings(self, form):
        c = self.open_and_get_cursor()
        for key, value in form.items():
            c.execute(
                "UPDATE face_recognition_settings SET value = ? WHERE key = ?", (value, key))
        # not so elegant, but unchecked HTML checkboxes are hard to handle
        checkbox_names = ["force_dnn_on_new", "flip_cam", "cache_unknown"]
        for box in checkbox_names:
            if box not in list(form.keys()):
                logging.info("setting off for: " + box)
                c.execute(
                    "UPDATE face_recognition_settings SET value = ? WHERE key = ?", ("off", box))
        self.commit_and_close_connection()

    def update_notification_settings(self, form):
        c = self.open_and_get_cursor()
        for key, value in form.items():
            c.execute(
                "UPDATE notification_settings SET value = ? WHERE key = ?", (value, key))
        # not so elegant, but unchecked HTML checkboxes are hard to handle
        checkbox_names = ["m_notif_spec", "m_notif_kno",
                          "m_notif_unk", "e_notif_spec", "e_notif_kno", "e_notif_unk"]
        for box in checkbox_names:
            if box not in list(form.keys()):
                logging.info("setting off for: " + box)
                c.execute(
                    "UPDATE notification_settings SET value = ? WHERE key = ?", ("off", box))
        self.commit_and_close_connection()

    # loads the face_recognition_settings table from the database into a dictionary
    def load_face_recognition_settings(self):
        c = self.open_and_get_cursor()
        d = dict()
        for row in c.execute("SELECT * FROM face_recognition_settings"):
            d[row[0]] = row[1]
        return d

    # loads the notification_settings table from the database into a dictionary
    def load_notification_settings(self):
        c = self.open_and_get_cursor()
        d = dict()
        for row in c.execute("SELECT * FROM notification_settings"):
            d[row[0]] = row[1]
        return d

    def change_thumbnail(self, name: str, pic: str):
        logging.info("Changing thumbnail for {}".format(name))
        Person.update(thumbnail=pic).where(Person.name == name).execute()

    def get_thumbnail(self, name: str) -> Person:
        logging.info("Getting thumbnail for {}".format(name))
        return Person.select(Person.thumbnail).where(Person.name == name).get()

    def empty_encodings(self):
        Encoding.delete().execute()
        logging.info("Deleted all encodings")

    def add_person(self, name: str, unknown: bool = True, thumbnail: str = None) -> Person:
        new_person = Person()
        new_person.name = name
        new_person.first_seen = datetime.now()
        new_person.last_seen = datetime.now()
        new_person.unknown = unknown
        new_person.thumbnail = Image.get_or_none(Image.name == thumbnail)
        new_person.save()
        logging.info("A new {} person was added with the name {}".format(
            'unkown' if unknown else 'known', name))
        return new_person

    def resolve_thumbnail(self, name: str) -> str:
        known_path = Path("Static", "dnn", name)
        unk_path = Path("Static", "unknown_pics", name)
        if known_path.exists():
            pic_list = list(known_path.iterdir())
            if len(pic_list) > 0:
                return Path(*pic_list[0].parts[1:])
        if unk_path.exists():
            pic_list = list(unk_path.iterdir())
            if len(pic_list) > 0:
                return Path(*pic_list[0].parts[1:])
        return None

    def add_encoding(self, name: str, encodingbytes: bytes):
        encoding = Encoding()
        encoding.encoding = encodingbytes
        person_by_name = Person.get_or_none(name=name)
        import pdb
        pdb.set_trace()
        encoding.person = person_by_name[0] if person_by_name is not None else self.add_person(
            name)
        encoding.save()
        logging.info("A new encoding was added for the person {}".format(name))

    def add_image(self, image_name: str, person_name: str, set_as_thumbnail: bool = False):
        image = Image()
        person_by_name = Person.get_or_none(name=person_name)
        if person_by_name is not None:
            image.person = person_by_name[0]
        else:
            raise Exception(
                'No matching person record was found for the name {}'.format(person_name))
        image.save()

        if set_as_thumbnail:
            person_by_name.thumbnail = image
            person_by_name.save()

        logging.info("{} image was added for the person {}".format(
            image_name, person_name))
