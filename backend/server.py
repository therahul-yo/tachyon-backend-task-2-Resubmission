from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime, sqlite3, os

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'secret_key')
DB_FILE = 'database.sqlite'

def query_database(sql_query, parameters=(), single_result=False, commit_changes=False):

    with sqlite3.connect(DB_FILE) as connection:
        cursor = connection.execute(sql_query, parameters)
        if commit_changes:
            connection.commit()
        results = cursor.fetchall()
    if single_result:
        return results[0] if results else None
    return results

def initialize_database():
 
    query_database('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT NOT NULL)''', commit_changes=True)
    query_database('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY, title TEXT, description TEXT DEFAULT '',
        status TEXT DEFAULT 'pending', user_id INTEGER, created_at TEXT, updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''', commit_changes=True)

initialize_database()

def token_required(func):
   
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = data['id']
        except:
            return jsonify({'error': 'Invalid token'}), 401
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.post('/api/auth/register')
def register():
    username = request.json.get('username')
    password = request.json.get('password')
    if not username or not password:
        return jsonify({'error': 'Missing fields'}), 400
  
    if query_database('SELECT 1 FROM users WHERE username=?', (username,), single_result=True):
        return jsonify({'error': 'Username exists'}), 400

    hashed_password = generate_password_hash(password)
    query_database('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password), commit_changes=True)
    user = query_database('SELECT id FROM users WHERE username=?', (username,), single_result=True)
    token = jwt.encode({'id': user[0], 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)}, app.config['SECRET_KEY'])
    return jsonify({'token': token})

@app.post('/api/auth/login')
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    user = query_database('SELECT id, password FROM users WHERE username=?', (username,), single_result=True)
    if not user or not check_password_hash(user[1], password):
        return jsonify({'error': 'Invalid credentials'}), 400
    token = jwt.encode({'id': user[0], 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)}, app.config['SECRET_KEY'])
    return jsonify({'token': token})


@app.get('/api/tasks')
@token_required
def get_tasks():
    search_term = request.args.get('search', '')
    tasks = query_database(
        'SELECT * FROM tasks WHERE user_id=? AND title LIKE ? ORDER BY id DESC',
        (request.user_id, f'%{search_term}%')
    )
    columns = ['id', 'title', 'description', 'status', 'user_id', 'created_at', 'updated_at']
    return jsonify([dict(zip(columns, task)) for task in tasks])

@app.post('/api/tasks')
@token_required
def add_task():
    data = request.json
    now = datetime.datetime.utcnow().isoformat()
    query_database(
        'INSERT INTO tasks (title, description, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
        (data.get('title'), data.get('description', ''), request.user_id, now, now),
        commit_changes=True
    )
    return get_tasks()

@app.put('/api/tasks/<int:task_id>')
@token_required
def edit_task(task_id):
    data = request.json
    now = datetime.datetime.utcnow().isoformat()
    query_database(
        'UPDATE tasks SET title=?, description=?, status=?, updated_at=? WHERE id=? AND user_id=?',
        (data.get('title'), data.get('description'), data.get('status', 'pending'), now, task_id, request.user_id),
        commit_changes=True
    )
    return get_tasks()

@app.delete('/api/tasks/<int:task_id>')
@token_required
def delete_task(task_id):
    query_database(
        'DELETE FROM tasks WHERE id=? AND user_id=?',
        (task_id, request.user_id),
        commit_changes=True
    )
    return get_tasks()

@app.patch('/api/tasks/<int:task_id>/complete')
@token_required
def complete_task(task_id):
    now = datetime.datetime.utcnow().isoformat()
    query_database(
        'UPDATE tasks SET status="done", updated_at=? WHERE id=? AND user_id=?',
        (now, task_id, request.user_id),
        commit_changes=True
    )
    return get_tasks()


@socketio.on('connect')
def handle_connect():
    print('🟢 Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('🔴 Client disconnected')

@socketio.on('join')
def handle_join(room):
    join_room(room)

@socketio.on('leave')
def handle_leave(room):
    leave_room(room)

@socketio.on('message')
def handle_message(data):
    emit('message', data, to=data.get('room'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8001)