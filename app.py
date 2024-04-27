import os
import requests
from dotenv import load_dotenv
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

# Initialize chat_history as an empty dictionary
chat_history = {}

# Load environment variables from a .env file (if it exists)
load_dotenv()

app = Flask(__name__)

# Set the logging level for your app
app.logger.setLevel(logging.DEBUG)  # Change to a higher level in production

# Configure upload settings
uploads_dir = os.path.join(app.instance_path, 'uploads')
os.makedirs(uploads_dir, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # Limit file size (consider your use case)

# Get the API key from the environment variable
api_key = os.getenv('CHATPDF_API_KEY')


# Function to add a PDF file via file upload and get the source ID
def add_pdf_via_file(file_path):
    headers = {'x-api-key': api_key}
    # Use 'with' statement for better resource management
    with open(file_path, 'rb') as file:
        files = {'file': ('file', file, 'application/octet-stream')}

        # Declare source_id and initialize to None
        source_id = None

        try:
            response = requests.post('https://api.chatpdf.com/v1/sources/add-file', headers=headers, files=files)

            if response.status_code == 200:
                data = response.json()  # Store the entire response data
                source_id = data.get('sourceId')  # Safely access 'sourceId'
                return source_id, None  # Return None for success
            else:
                error_message = "Failed to upload PDF: {} ({})".format(response.status_code, response.text)
                return None, error_message

        except requests.exceptions.RequestException as e:
            error_message = "Error uploading file: {}".format(str(e))
            return None, error_message


# Function to send a chat message to a PDF file
def send_chat_message(source_id, user_message):
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json'
    }

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = {
        'sourceId': source_id,
        'messages': [
            {'role': 'user', 'content': user_message, 'timestamp': timestamp}
        ]
    }

    try:
        response = requests.post('https://api.chatpdf.com/v1/chats/message', headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()['content']
            return result, None  # Return the result and None for success

        else:
            error_message = "Failed to send message: {} ({})".format(response.status_code, response.text)
            return None, error_message

    except requests.exceptions.RequestException as e:
        error_message = "Error sending chat message: {}".format(str(e))
        return None, error_message


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

    file_path = os.path.join(uploads_dir, file.filename)
    file.save(file_path)

    source_id, error_message = add_pdf_via_file(file_path)

    if error_message:
        flash(error_message, 'error')
        return redirect(url_for('index'))

    chat_history[source_id] = []
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
            history.append({'role': 'user', 'content': user_message, 'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            history.append({'role': 'assistant', 'content': chat_response, 'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            chat_history[source_id] = history

    return render_template('chat.html', source_id=source_id, history=history)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Use PORT environment variable if it's set, otherwise default to 5000
    app.run(host='0.0.0.0', port=port)
