from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Catalog, MenuItem, User
from flask import session as login_session
import random
import string
import time
import datetime

# IMPORTS FOR THIS STEP
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog Menu Application"


# Connect to Database and create database session
engine = create_engine('sqlite:///catalogs.db?check_same_thread=False')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token
@app.route('/login/')
@app.route('/login')
def showLogin():
    state = ''.join(
        random.choice(string.ascii_uppercase + string.digits) for x in range(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)

@app.route('/gconnect/', methods=['POST'])
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code, now compatible with Python3
    #request.get_data()
    code = request.data.decode('utf-8')

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    # Submit request, parse response - Python3 compatible
    h = httplib2.Http()
    response = h.request(url, 'GET')[1]
    str_response = response.decode('utf-8')
    result = json.loads(str_response)

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    return output

# User Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    print('User is: ' + user.name + " --- " + str(user.id))
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect/')
@app.route('/gdisconnect')
def gdisconnect():
        # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    print(url)
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print(result['status'])
    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# Show all catalogs
@app.route('/')
@app.route('/catalog')
@app.route('/catalog/')
def showCatalogs():
    catalogs = session.query(Catalog).order_by(asc(Catalog.name))
    items = session.query(MenuItem).order_by(desc(MenuItem.create_date))
    if 'username' not in login_session:
        return render_template('publicrestaurants.html', catalogs=catalogs, items=items)
    else:
        return render_template('restaurants.html', catalogs=catalogs, items=items)

# JSON APIs to view Catalog Information
@app.route('/catalog/<int:catalog_id>/menu/JSON')
def catalogMenuJSON(catalog_id):
    catalog = session.query(Catalog).filter_by(id=catalog_id).one()
    items = session.query(MenuItem).filter_by(
        catalog_id=catalog_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/catalog.json')
def catalogsJSON():
    catalogs = session.query(Catalog).all()
    return jsonify(catalogs=[r.serialize for r in catalogs])

@app.route('/items.json')
def itemsJSON():
    items = session.query(MenuItem).all()
    return jsonify(items=[r.serialize for r in items])


@app.route('/item/new/', methods=['GET', 'POST'])
def newItem():
    catalogs = session.query(Catalog).all()
    
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        selectedCatalogDropdown = request.form.get('category')
        selectedCatalogId = str(selectedCatalogDropdown)
        selectedCatalog = session.query(Catalog).filter_by(id=int(selectedCatalogId)).one()

        newItem = MenuItem(user_id=login_session['user_id'], name=request.form['name'], description=request.form['description'],
                     price="", course="Item", catalog=selectedCatalog, create_date=datetime.datetime.now())
        session.add(newItem)
        flash('New Item %s Successfully Created' % newItem.name)
        session.commit()
        return redirect(url_for('showCatalogs'))
    else:
        return render_template('newmenuitem.html', catalogs=catalogs)

@app.route('/catalog/<string:catalog_name>')
@app.route('/catalog/<string:catalog_name>/')
@app.route('/catalog/<string:catalog_name>/items/')
def showItems(catalog_name):
    catalog = session.query(Catalog).filter_by(name=catalog_name).one()
    creator = getUserInfo(catalog.user_id)
    items = session.query(MenuItem).filter_by(
        catalog_id=catalog.id).all()
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicmenu.html', items=items, catalog=catalog, creator=creator)
    else:
        return render_template('menu.html', items=items, catalog=catalog, creator=creator)

@app.route('/catalog/<string:catalog_name>/<string:item_name>')
@app.route('/catalog/<string:catalog_name>/<string:item_name>/')
def showItemDetail(catalog_name, item_name):
    catalog = session.query(Catalog).filter_by(name=catalog_name).one()
    item = session.query(MenuItem).filter_by(
        catalog_id=catalog.id, name=item_name).one()
    creator = getUserInfo(item.user_id)
    
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicitemdetail.html', item=item, catalog=catalog, creator=creator)
    else:
        return render_template('itemdetail.html', item=item, catalog=catalog, creator=creator)

@app.route('/catalog/<int:catalog_id>/menu/<int:menu_id>/edit/', methods=['GET', 'POST'])
@app.route('/catalog/<int:catalog_id>/menu/<int:menu_id>/edit', methods=['GET', 'POST'])
def editMenuItem(catalog_id, menu_id):
    return """<p>asasda</p>"""

@app.route('/catalog/<int:catalog_id>/menu/<int:menu_id>/delete/', methods=['GET', 'POST'])
@app.route('/catalog/<int:catalog_id>/menu/<int:menu_id>/delete', methods=['GET', 'POST'])
def deleteMenuItem(catalog_id, menu_id):
    return """<p>asasda</p>"""

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)