from flask import Flask, Blueprint, request, session, jsonify
from flask_restful import Api, Resource
from flask_cors import CORS
from flask_mail import Mail, Message
from models import db, User, Note, ContactMessage
from schemas import UserSchema, NoteSchema, ContactMessageSchema
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True

import logging
from flask_cors import cross_origin
mail = Mail(app)


logging.basicConfig(level=logging.INFO)


api_bp = Blueprint('api', __name__)
api = Api(api_bp)

user_schema = UserSchema()
note_schema = NoteSchema()
notes_schema = NoteSchema(many=True)
contact_message_schema = ContactMessageSchema()

def respond_with_error(message, status_code):
    response = {'error': message}
    return jsonify(response), status_code

def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        logging.info(f'Current user ID: {user_id}')
        return User.query.get(user_id)
    logging.info('No user ID found in session.')
    return None

class Signup(Resource):
    @cross_origin()
    def post(self):
        data = request.get_json()
        if not data or 'email' not in data or 'password' not in data:
            return respond_with_error('Email and password required', 400)

        
        if User.query.filter_by(email=data['email']).first():
            return respond_with_error('User already exists', 400)

        
        new_user = User(email=data['email'])
        new_user.password = data['password']  
        db.session.add(new_user)
        db.session.commit()
        
        return user_schema.dump(new_user), 201

    @cross_origin()
    def get(self):
        users = User.query.all()
        return user_schema.dump(users, many=True), 200

class Login(Resource):
    @cross_origin(supports_credentials=True)
    def post(self):
        
        data = request.get_json()

        
        if not data or 'email' not in data or 'password' not in data:
            return respond_with_error('Email and password required', 400)

       
        user = User.query.filter_by(email=data['email']).first()

       
        if not user or not user.check_password(data['password']):
            return respond_with_error('Invalid email or password', 401)

        
        session['user_id'] = user.id

        
        return user_schema.dump(user), 200

class ForgotPassword(Resource):
    def post(self):
        data = request.get_json()
        logging.info(f'Received forgot password request: {data}')

        if not data or 'email' not in data:
            logging.warning('Email required for password reset')
            return {"error": "Email required"}, 400

        user = User.query.filter_by(email=data['email']).first()
        if not user:
            logging.warning('User not found for password reset')
            return {"error": "User not found"}, 404

        
        reset_token = "placeholder_for_reset_token"  
        reset_link = f'http://localhost:5000/reset-password/{reset_token}'  
        msg = Message('Password Reset Request', sender='your_email@gmail.com', recipients=[data['email']])
        msg.body = f'Please use the following link to reset your password: {reset_link}'
        try:
            mail.send(msg)
            logging.info(f'Password reset link sent to {data["email"]}')
            return {"message": "Password reset link sent"}, 200
        except Exception as e:
            logging.error(f'Error sending email: {e}')
            return {"error": "Failed to send password reset link"}, 500

class Logout(Resource):
    @cross_origin()
    def delete(self):
        session.pop('user_id', None)
        return {}, 204

class CheckSession(Resource):
    @cross_origin()
    def get(self):
        user = get_current_user()  
        if user:
            return user_schema.dump(user), 200  
        return respond_with_error('Unauthorized', 401)  


class Notes(Resource):
    @cross_origin(supports_credentials=True)
    def get(self):
        user = get_current_user()
        if not user:
            return respond_with_error('Unauthorized', 401)

        notes = Note.query.filter_by(user_id=user.id).all()
        return notes_schema.dump(notes), 200

    @cross_origin(supports_credentials=True)
    def post(self):
        user = get_current_user()
        if not user:
            return respond_with_error('Unauthorized', 401)

        data = request.get_json()
        if not data or 'title' not in data or 'content' not in data:
            return respond_with_error('Title and content required', 400)

        new_note = Note(title=data['title'], content=data['content'], user_id=user.id)
        db.session.add(new_note)

        try:
            db.session.commit()
            return note_schema.dump(new_note), 201
        except Exception as e:
            db.session.rollback()
            logging.error(f'Error creating note: {e}')
            return respond_with_error('Failed to create note', 500)

    @cross_origin(supports_credentials=True)
    def put(self, note_id):
        user = get_current_user()
        if not user:
            return respond_with_error('Unauthorized', 401)

        note = Note.query.get(note_id)
        if not note:
            return respond_with_error('Note not found', 404)

        if note.user_id != user.id:
            return respond_with_error('Not authorized to update this note', 403)

        data = request.get_json()
        if not data or 'title' not in data or 'content' not in data:
            return respond_with_error('Title and content required', 400)

        note.title = data['title']
        note.content = data['content']

        try:
            db.session.commit()
            return note_schema.dump(note), 200
        except Exception as e:
            db.session.rollback()
            logging.error(f'Error updating note: {e}')
            return respond_with_error('Failed to update note', 500)

    @cross_origin(supports_credentials=True)
    def patch(self, note_id):
        user = get_current_user()
        if not user:
           logging.warning('Unauthorized access attempt to PATCH')
           return respond_with_error('Unauthorized', 401)

        note = Note.query.get(note_id)
        if not note:
           logging.warning(f'Note with ID {note_id} not found')
           return respond_with_error('Note not found', 404)


        if note.user_id != user.id:
           logging.warning(f'User {user.id} not authorized to update note {note_id}')
           return respond_with_error('Not authorized to update this note', 403)

        data = request.get_json()
        logging.info(f'PATCH data received: {data}')

        if data:
           if 'title' in data:
            note.title = data['title']
           if 'content' in data:
            note.content = data['content']

            note.user_id = user.id  

        try:
           db.session.commit()
           logging.info(f'Note with ID {note_id} updated successfully')
           return note_schema.dump(note), 200
        except Exception as e:
           db.session.rollback()
           logging.error(f'Error updating note: {e}')
           return respond_with_error('Failed to update note', 500)

    @cross_origin(supports_credentials=True)
    def delete(self, note_id):
        user = get_current_user()
        if not user:
            logging.warning('Unauthorized delete attempt')
            return respond_with_error('Unauthorized', 401)

        note = Note.query.get(note_id)
        if not note:
            logging.warning(f'Note with ID {note_id} not found')
            return respond_with_error('Note not found', 404)

        if note.user_id != user.id:
            logging.warning(f'User {user.id} not authorized to delete note {note_id}')
            return respond_with_error('Not authorized to delete this note', 403)

        db.session.delete(note)

        try:
            db.session.commit()
            logging.info(f'Note with ID {note_id} deleted successfully')
            return {'message': 'Note deleted successfully'}, 204
        except Exception as e:
            db.session.rollback()
            logging.error(f'Error deleting note: {e}')
            return respond_with_error('Failed to delete note', 500)

class NoteResource(Resource):
    @cross_origin(supports_credentials=True)
    def get(self, note_id):
        user = get_current_user()
        if not user:
            return respond_with_error('Unauthorized', 401)

        note = Note.query.get(note_id)
        if note and note.user_id == user.id:
            return note_schema.dump(note), 200
        return respond_with_error('Note not found or forbidden', 404)

    @cross_origin(supports_credentials=True)
    def patch(self, note_id):
        user = get_current_user()
        if not user:
            return respond_with_error('Unauthorized', 401)

        note = Note.query.get(note_id)
        if not note or note.user_id != user.id:
            return respond_with_error('Note not found or forbidden', 404)

        data = request.get_json()
        note.title = data.get('title', note.title)
        note.content = data.get('content', note.content)

        try:
            db.session.commit()
            return note_schema.dump(note), 200
        except Exception as e:
            db.session.rollback()
            logging.error(f'Error updating note: {e}')
            return respond_with_error('Failed to update note', 500)

    @cross_origin()
    def delete(self, note_id):
        user = get_current_user()
        if not user:
            return respond_with_error('Unauthorized', 401)

        note = Note.query.get(note_id)
        if note and note.user_id == user.id:
            db.session.delete(note)
            db.session.commit()
            return {}, 204
        return respond_with_error('Note not found or forbidden', 404)

class NoteByTitle(Resource):
    @cross_origin()
    def get(self, title):
        user = get_current_user()
        if not user:
            return respond_with_error('Unauthorized', 401)

        note = Note.query.filter_by(title=title, user_id=user.id).first()  # Adjust query
        if note:
            return note_schema.dump(note), 200
        return respond_with_error('Note not found or forbidden', 404)

class Contact(Resource):
    @cross_origin()
    def post(self):
        data = request.get_json()
        if not data or 'name' not in data or 'email' not in data or 'subject' not in data or 'message' not in data:
            return respond_with_error('All fields are required', 400)

        contact_message = ContactMessage(
            name=data['name'],
            email=data['email'],
            subject=data['subject'],
            message=data['message']
        )

        db.session.add(contact_message)

        try:
            db.session.commit()
            return contact_message_schema.dump(contact_message), 201
        except Exception as e:
            db.session.rollback()
            logging.error(f'Error saving contact message: {e}')
            return respond_with_error('Failed to send message', 500)

class Users(Resource):
    @cross_origin()
    def get(self):
        users = User.query.all()  
        return user_schema.dump(users, many=True), 200  

api.add_resource(Signup, '/signup')
api.add_resource(Login, '/login')
api.add_resource(ForgotPassword, '/api/forgot-password')
api.add_resource(Logout, '/logout')
api.add_resource(CheckSession, '/check_session')
api.add_resource(Notes, '/notes')
api.add_resource(NoteResource, '/notes/<int:note_id>')
api.add_resource(NoteByTitle, '/notes/title/<string:title>')  
api.add_resource(Contact, '/contact')
api.add_resource(Users, '/users')  

@api_bp.errorhandler(Exception)
def handle_exception(e):
    logging.error(f'Unhandled exception: {str(e)}')
    return respond_with_error('Internal Server Error', 500)

