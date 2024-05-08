import os
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask_caching import Cache
import logging
import secrets

# Initialize chat_history as an empty dictionary
chat_history = {}

# Load environment variables from a .env file (if it exists)
load_dotenv()

app = Flask(__name__)

# Generate a secure secret key
app.secret_key = secrets.token_urlsafe(32)

# Set the logging level for your app
app.logger.setLevel(logging.DEBUG)  # Change to a higher level in production

# Configure upload settings
uploads_dir = os.path.join(app.instance_path, 'uploads')
os.makedirs(uploads_dir, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # Limit file size (consider your use case)
app.config['UPLOAD_FOLDER'] = uploads_dir

# Get the API key from the environment variable
api_key = os.getenv('CHATPDF_API_KEY')

# Initialize Flask-Caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        flash('Please select a valid file.', 'error')
        return redirect(request.url)

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    source_id, error_message = add_pdf_via_file(file_path)

    if error_message:
        flash(error_message, 'error')
        return redirect(url_for('index'))

    chat_history[source_id] = []
    flash('File uploaded successfully.', 'success')  # User feedback
    return redirect(url_for('chat', source_id=source_id))


@app.route('/upload_url', methods=['POST'])
def upload_url():
    url = request.form['url']
    source_id, error_message = add_pdf_via_url(url)

    if error_message:
        flash(error_message, 'error')
        return redirect(url_for('index'))

    chat_history[source_id] = []
    flash('File uploaded successfully.', 'success')  # User feedback
    return redirect(url_for('chat', source_id=source_id))


@app.route('/chat/<source_id>', methods=['GET', 'POST'])
def chat(source_id):
    history = chat_history.get(source_id, [])

    if request.method == 'POST':
        user_message = request.form.get('user_message')
        chat_response, error_message = send_chat_message(source_id, user_message)

        if error_message:
            flash(error_message, 'error')
        else:
            timestamp = format_timestamp()
            history.append({'role': 'user', 'content': user_message, 'timestamp': timestamp})
            history.append({'role': 'assistant', 'content': chat_response, 'timestamp': timestamp})

    return render_template('chat.html', source_id=source_id, history=history)


@cache.memoize(timeout=50)  # Cache API responses for 50 seconds
def add_pdf_via_file(file_path):
    headers = {'x-api-key': api_key}
    files = {'file': ('file', open(file_path, 'rb'), 'application/octet-stream')}

    try:
        response = requests.post('https://api.chatpdf.com/v1/sources/add-file', headers=headers, files=files)
        response.raise_for_status()
        data = response.json()
        source_id = data.get('sourceId')
        return source_id, None

    except requests.exceptions.RequestException as e:
        error_message = f"Error uploading file: {str(e)}"
        return None, error_message


@cache.memoize(timeout=50)  # Cache API responses for 50 seconds
def add_pdf_via_url(url):
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json'
    }
    data = {'url': url}

    try:
        response = requests.post('https://api.chatpdf.com/v1/sources/add-url', headers=headers, json=data)
        response.raise_for_status()
        data = response.json()
        source_id = data['sourceId']
        return source_id, None

    except requests.exceptions.RequestException as e:
        error_message = f"Error uploading file: {str(e)}"
        return None, error_message

    except KeyError:
        error_message = "Invalid response from the API. Missing 'sourceId' key."
        return None, error_message


def send_chat_message(source_id, user_message):
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json'
    }

    timestamp = format_timestamp()

    data = {
        'sourceId': source_id,
        'messages': [
            {'role': 'user', 'content': user_message, 'timestamp': timestamp}
        ]
    }

    try:
        response = requests.post('https://api.chatpdf.com/v1/chats/message', headers=headers, json=data)
        response.raise_for_status()
        result = response.json()['content']
        return result, None

    except requests.exceptions.RequestException as e:
        error_message = f"Error sending chat message: {str(e)}"
        return None, error_message


def format_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))  # Use the PORT environment variable if available
    app.run(debug=False, host='0.0.0.0', port=port)
