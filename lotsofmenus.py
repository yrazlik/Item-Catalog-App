from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import time
import datetime

from database_setup import Catalog, Base, MenuItem, User

engine = create_engine('sqlite:///catalogs.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()

# Create dummy user
User1 = User(name="Yasin Razlik", email="yrazlik@sabanciuniv.edu",
             picture='https://pbs.twimg.com/profile_images/717670913689329664/EUWoBRtN.jpg')
session.add(User1)
session.commit()

catalog1 = Catalog(user_id=1, name="Soccer")

session.add(catalog1)
session.commit()

menuItem2 = MenuItem(user_id=1, name="Ball", description="A Ball",
                     price="$7.50", course="Item", catalog=catalog1, create_date=datetime.datetime.now())

session.add(menuItem2)
session.commit()


menuItem1 = MenuItem(user_id=1, name="Shoes", description="You hit the ball with it",
                     price="$2.99", course="Item", catalog=catalog1, create_date=datetime.datetime.now())

session.add(menuItem1)
session.commit()

print "added menu items!"