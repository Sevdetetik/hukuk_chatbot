import os
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
import time
import markdown
import base64
import random       
from flask_migrate import Migrate

# Flask uygulamasını ve veritabanını yapılandır
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SECRET_KEY'] = "os.urandom(24)"

app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# OpenAI istemcisini API anahtarınızla başlat
client = OpenAI(api_key="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")

# Veritabanı modellerini tanımla
class VectorStore(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)

class Assistant(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)
    instructions = db.Column(db.String)
    tools = db.Column(db.String)
    vector_store_id = db.Column(db.String, db.ForeignKey('vector_store.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    # Hangi arayüz için kullanılacağını belirten alan
    interface_type = db.Column(db.String, default="chat")  # "chat", "satso", "aris" olabilir

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    threads = db.relationship('Thread', backref='user', lazy=True)

# Thread modelini güncelleyelim
class Thread(db.Model):
    id = db.Column(db.String, primary_key=True)
    session_id = db.Column(db.String)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Message(db.Model):
    id = db.Column(db.String, primary_key=True)
    thread_id = db.Column(db.String, db.ForeignKey('thread.id'))
    content = db.Column(db.String)
    role = db.Column(db.String) 

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Veritabanı tablolarını oluştur (yalnızca bir kez çalıştırılmalıdır)
with app.app_context():
    db.create_all()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin'))
        flash('Invalid username or password', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            return 'Username already exists'
            
        hashed_password = generate_password_hash(password)
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return redirect(url_for('chat'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

#main.html için rota
@app.route('/')
def home():
    return render_template('main.html')

# Yönetici paneli rotaları
@app.route('/admin')
@admin_required
def admin():
    assistants = Assistant.query.all() # Asistanları sorgula
    return render_template('admin.html', assistants=assistants)

@app.route('/select_assistant', methods=['POST'])
@admin_required
def select_assistant():
    assistant_id = request.form['assistant_id']
    interface_type = request.form['interface_type']
    
    # İlgili arayüz türü için tüm asistanları deaktif yap
    Assistant.query.filter_by(interface_type=interface_type).update({Assistant.is_active: False})
    
    # Seçilen asistanı aktif yap ve arayüz türünü ayarla
    assistant = Assistant.query.get(assistant_id)
    if assistant:
        assistant.is_active = True
        assistant.interface_type = interface_type
        db.session.commit()
        
    return redirect(url_for('admin'))

@app.route('/admin/vector_stores')
@admin_required
def vector_stores():
    vector_stores = VectorStore.query.all()
    return render_template('vector_stores.html', vector_stores=vector_stores)

@app.route('/admin/vector_stores/create', methods=['POST'])
@admin_required
def create_vector_store():
    name = request.form['name']
    vector_store = client.vector_stores.create(name=name)
    db_vector_store = VectorStore(id=vector_store.id, name=name)
    db.session.add(db_vector_store)
    db.session.commit()
    return redirect(url_for('vector_stores'))

@app.route('/admin/vector_stores/delete/<id>', methods=['POST'])
@admin_required
def delete_vector_store(id):
    client.vector_stores.delete(vector_store_id=id)
    vector_store = VectorStore.query.get(id)
    db.session.delete(vector_store)
    db.session.commit()
    return redirect(url_for('vector_stores'))

@app.route('/admin/vector_stores/edit/<id>')
@admin_required
def edit_vector_store(id):
    vector_store = VectorStore.query.get(id)
    return render_template('edit_vector_store.html', vector_store=vector_store)

@app.route('/admin/vector_stores/update/<id>', methods=['POST'])
@admin_required
def update_vector_store(id):
    name = request.form['name']
    client.vector_stores.update(vector_store_id=id, name=name)
    vector_store = VectorStore.query.get(id)
    vector_store.name = name
    db.session.commit()
    return redirect(url_for('vector_stores'))

@app.route('/admin/vector_stores/files/<vector_store_id>')
@admin_required
def vector_store_files(vector_store_id):
    page = request.args.get('page', 1, type=int)  # Sayfa numarasını al, varsayılan 1
    limit = 10  # Sayfa başına dosya sayısı
    offset = (page - 1) * limit

    all_files = []
    has_more = True
    after = None
    
    while has_more:
      files = client.vector_stores.files.list(
          vector_store_id=vector_store_id,
          limit=limit + 1,  # Bir sonraki sayfa var mı kontrolü için +1
          after=after
      )

      for file in files.data:
          try:
              file_info = client.files.retrieve(file.id)
              file.filename = file_info.filename
          except Exception as e:
              file.filename = f"Unknown filename (ID: {file.id})"
              print(f"Error retrieving file info: {str(e)}")

      all_files.extend(files.data)

      if files.has_more:
          after = files.last_id
      else:
          has_more = False

    # Sayfalama için dosyaları dilimle
    paginated_files = all_files[offset:offset + limit]

    # Toplam sayfa sayısını hesapla
    total_files = len(all_files)
    total_pages = (total_files + limit - 1) // limit

    return render_template('vector_store_files.html',
                           files=paginated_files,
                           vector_store_id=vector_store_id,
                           page=page,
                           total_pages=total_pages,
                           total_files=total_files)

@app.route('/admin/vector_stores/<vector_store_id>/upload_file', methods=['POST'])
@admin_required
def upload_file_to_vector_store(vector_store_id):
    ALLOWED_EXTENSIONS = {
        'c', 'cpp', 'cs', 'css', 'doc', 'docx', 'go', 'html',
        'java', 'js', 'json', 'md', 'pdf', 'php', 'pptx',
        'py', 'rb', 'sh', 'tex', 'ts', 'txt'
    }
    
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    files = request.files.getlist('file')
    uploaded_files = []
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            try:
                file_content = file.read()
                
                # Dosyayı OpenAI'ye yükle
                openai_file = client.files.create(
                    file=(file.filename, file_content),
                    purpose="assistants"
                )

                # Vector store'a ekle
                vector_store_file = client.vector_stores.files.create(
                    vector_store_id=vector_store_id,
                    file_id=openai_file.id
                )
                
                uploaded_files.append(file.filename)
                
            except Exception as e:
                flash(f'Error uploading file {file.filename}: {str(e)}', 'error')
        else:
            flash(f'Invalid file type: {file.filename}', 'error')
    
    if uploaded_files:
        flash(f'Successfully uploaded files: {", ".join(uploaded_files)}', 'success')
            
    return redirect(url_for('vector_store_files', vector_store_id=vector_store_id))

@app.route('/admin/vector_stores/<vector_store_id>/delete_file/<file_id>', methods=['POST'])
@admin_required
def delete_file_from_vector_store(vector_store_id, file_id):
    client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
    return redirect(url_for('vector_store_files', vector_store_id=vector_store_id))

@app.route('/admin/assistants')
@admin_required
def assistants():
    assistants = Assistant.query.all()
    vector_stores = VectorStore.query.all()
    return render_template('assistants.html', assistants=assistants, vector_stores=vector_stores)

@app.route('/admin/assistants/create', methods=['POST'])
@admin_required
def create_assistant():
    name = request.form['name']
    instructions = request.form['instructions']
    tools = request.form.getlist('tools')
    vector_store_id = request.form.get('vector_store_id')
    interface_type = request.form.get('interface_type', 'chat')  # Varsayılan olarak "chat"

    # Araçları API'nin beklediği formata dönüştür
    formatted_tools = []
    for tool in tools:
        if tool == "file_search":
            formatted_tools.append({"type": "file_search"})
        elif tool == "code_interpreter":
            formatted_tools.append({"type": "code_interpreter"})

    # file_search aracı seçiliyse vector_store_id'yi ayarla
    tool_resources = {}
    if "file_search" in tools and vector_store_id:
        tool_resources = {"file_search": {"vector_store_ids": [vector_store_id]}}

    # OpenAI API ile asistan oluştur
    assistant = client.beta.assistants.create(
        name=name,
        instructions=instructions,
        tools=formatted_tools,
        model="gpt-4o-mini",
        tool_resources=tool_resources
    )

    # Eğer seçilen arayüz türü için başka aktif asistan yoksa bu asistanı aktif yap
    is_active = not Assistant.query.filter_by(interface_type=interface_type, is_active=True).first()

    # Veritabanına kaydet
    db_assistant = Assistant(
        id=assistant.id,
        name=name,
        instructions=instructions,
        tools=str(tools),
        vector_store_id=vector_store_id,
        interface_type=interface_type,
        is_active=is_active
    )
    db.session.add(db_assistant)
    db.session.commit()

    return redirect(url_for('assistants'))

@app.route('/admin/assistants/delete/<id>', methods=['POST'])
@admin_required
def delete_assistant(id):
    client.beta.assistants.delete(assistant_id=id)
    assistant = Assistant.query.get(id)
    db.session.delete(assistant)
    db.session.commit()
    return redirect(url_for('assistants'))

@app.route('/chat/<thread_id>', methods=['GET', 'POST'])
@app.route('/chat', methods=['GET', 'POST'])
def chat(thread_id=None):
    if request.method == 'GET' and not thread_id:
        session.pop('thread_id', None)
        
    if request.method == 'POST':
        user_message = request.form['message']
        
        # "chat" arayüzü için aktif asistanı bul
        active_assistant = Assistant.query.filter_by(is_active=True, interface_type="chat").first()
        if not active_assistant:
            return jsonify({"error": "No active assistant found for chat interface"}), 500

        # Thread ID kontrolü
        if thread_id:
            current_thread_id = thread_id
        else:
            current_thread_id = session.get('thread_id')
            if not current_thread_id:
                thread = client.beta.threads.create()
                current_thread_id = thread.id
                session['thread_id'] = current_thread_id

                db_thread = Thread(
                    id=current_thread_id,
                    user_id=current_user.id if current_user.is_authenticated else None
                )
                db.session.add(db_thread)
                db.session.commit()

        try:
            # Kullanıcı mesajını thread'e ekle
            message = client.beta.threads.messages.create(
                thread_id=current_thread_id,
                role="user",
                content=user_message
            )

            db_user_message = Message(
                id=message.id,
                thread_id=current_thread_id,
                content=user_message,
                role="user"
            )
            db.session.add(db_user_message)
            db.session.commit()

            run = client.beta.threads.runs.create(
                thread_id=current_thread_id,
                assistant_id=active_assistant.id
            )

            while True:
                run = client.beta.threads.runs.retrieve(
                    thread_id=current_thread_id,
                    run_id=run.id
                )
                if run.status == "completed":
                    break
                elif run.status == "failed":
                    return jsonify({"error": "Assistant response failed"}), 500

            messages = client.beta.threads.messages.list(
                thread_id=current_thread_id,
                order="desc",
                limit=1
            )

            if not messages.data:
                return jsonify({"error": "No response from assistant"}), 500

            assistant_response = messages.data[0].content[0].text.value

            db_message = Message(
                id=messages.data[0].id,
                thread_id=current_thread_id,
                content=assistant_response,
                role="assistant"
            )
            db.session.add(db_message)
            db.session.commit()

            return jsonify({
                'messages': [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_response}
                ]
            })

        except Exception as e:
            print(f"Error in chat: {str(e)}")
            return jsonify({"error": str(e)}), 500

    # GET isteği için chat geçmişini al
    messages = []
    current_thread_id = thread_id or session.get('thread_id')
    
    if current_thread_id:
        db_messages = Message.query.filter_by(thread_id=current_thread_id).order_by(Message.id).all()
        # Message objelerini dictionary'lere dönüştür
        messages = [{"role": msg.role, "content": msg.content} for msg in db_messages]
    
    # Kullanıcının tüm thread'lerini al
    user_threads = []
    if current_user.is_authenticated:
        db_threads = Thread.query.filter_by(user_id=current_user.id).all()
        for thread in db_threads:
            first_message = Message.query.filter_by(thread_id=thread.id).first()
            thread_data = {
                "id": thread.id,
                "preview": first_message.content[:50] if first_message else "New conversation"
            }
            user_threads.append(thread_data)

    return render_template(
        'chat.html', 
        messages=messages, 
        threads=user_threads, 
        current_thread_id=current_thread_id
    )

@app.route('/satso', methods=['GET', 'POST'])
def satso_chat():
    if request.method == 'GET':
        # Her GET isteğinde yeni bir thread oluştur
        thread = client.beta.threads.create()
        session['satso_thread_id'] = thread.id  # Thread ID'yi session'a kaydet
        current_thread_id = thread.id

        # Yeni thread'i veritabanına kaydet
        db_thread = Thread(
            id=current_thread_id,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(db_thread)
        db.session.commit()

    elif request.method == 'POST':
        user_message = request.form['message']

        # "satso" arayüzü için aktif asistanı bul
        active_assistant = Assistant.query.filter_by(is_active=True, interface_type="satso").first()
        if not active_assistant:
            return jsonify({"error": "No active assistant found for SATSO interface"}), 500

        # Session'dan thread_id'yi al
        current_thread_id = session.get('satso_thread_id')
        if not current_thread_id:
            return jsonify({"error": "Thread ID not found in session"}), 500

        try:
            # Kullanıcı mesajını thread'e ekle
            message = client.beta.threads.messages.create(
                thread_id=current_thread_id,
                role="user",
                content=user_message
            )

            db_user_message = Message(
                id=message.id,
                thread_id=current_thread_id,
                content=user_message,
                role="user"
            )
            db.session.add(db_user_message)
            db.session.commit()

            # Run oluştur
            run = client.beta.threads.runs.create(
                thread_id=current_thread_id,
                assistant_id=active_assistant.id
            )

            # Run'ın tamamlanmasını bekle (zaman aşımı ile)
            timeout = time.time() + 60  # 60 saniye zaman aşımı
            while True:
                try:
                    run = client.beta.threads.runs.retrieve(
                        thread_id=current_thread_id,
                        run_id=run.id
                    )
                except Exception as e:
                    print(f"Error retrieving run: {str(e)}")
                    return jsonify({"error": "Error retrieving assistant response"}), 500

                if run.status == "completed":
                    break
                elif run.status == "failed":
                    print(f"Run failed: {run.last_error}")
                    return jsonify({"error": "Assistant response failed", "details": run.last_error}), 500
                elif time.time() > timeout:
                    print("Timeout while waiting for assistant response")
                    return jsonify({"error": "Timeout waiting for assistant response"}), 500

                time.sleep(1)  # 1 saniye bekle

            messages = client.beta.threads.messages.list(
                thread_id=current_thread_id,
                order="desc",
                limit=1
            )

            if not messages.data:
                return jsonify({"error": "No response from assistant"}), 500

            assistant_response = messages.data[0].content[0].text.value

            db_message = Message(
                id=messages.data[0].id,
                thread_id=current_thread_id,
                content=assistant_response,
                role="assistant"
            )
            db.session.add(db_message)
            db.session.commit()

            return jsonify({
                'messages': [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_response}
                ]
            })

        except Exception as e:
            print(f"Error in chat: {str(e)}")
            return jsonify({"error": str(e)}), 500

    # GET isteği için parametreleri hazırla
    messages = []
    current_thread_id = None # Yeni oluşturulan thread ID atanacak

    return render_template(
        'satso.html',
        messages=messages,
        current_thread_id=current_thread_id
    )

@app.route('/aris', methods=['GET', 'POST'])
def aris_chat():
    if request.method == 'GET':
        # Her GET isteğinde yeni bir thread oluştur
        thread = client.beta.threads.create()
        session['aris_thread_id'] = thread.id  # Thread ID'yi session'a kaydet
        current_thread_id = thread.id

        # Yeni thread'i veritabanına kaydet
        db_thread = Thread(
            id=current_thread_id,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(db_thread)
        db.session.commit()

    elif request.method == 'POST':
        user_message = request.form['message']

        # "aris" arayüzü için aktif asistanı bul
        active_assistant = Assistant.query.filter_by(is_active=True, interface_type="aris").first()
        if not active_assistant:
            return jsonify({"error": "No active assistant found for ARIS interface"}), 500

        # Session'dan thread_id'yi al
        current_thread_id = session.get('aris_thread_id')
        if not current_thread_id:
            return jsonify({"error": "Thread ID not found in session"}), 500

        try:
            # Kullanıcı mesajını thread'e ekle
            message = client.beta.threads.messages.create(
                thread_id=current_thread_id,
                role="user",
                content=user_message
            )

            db_user_message = Message(
                id=message.id,
                thread_id=current_thread_id,
                content=user_message,
                role="user"
            )
            db.session.add(db_user_message)
            db.session.commit()

            # Run oluştur
            run = client.beta.threads.runs.create(
                thread_id=current_thread_id,
                assistant_id=active_assistant.id
            )

            # Run'ın tamamlanmasını bekle (zaman aşımı ile)
            timeout = time.time() + 60  # 60 saniye zaman aşımı
            while True:
                try:
                    run = client.beta.threads.runs.retrieve(
                        thread_id=current_thread_id,
                        run_id=run.id
                    )
                except Exception as e:
                    print(f"Error retrieving run: {str(e)}")
                    return jsonify({"error": "Error retrieving assistant response"}), 500

                if run.status == "completed":
                    break
                elif run.status == "failed":
                    print(f"Run failed: {run.last_error}")
                    return jsonify({"error": "Assistant response failed", "details": run.last_error}), 500
                elif time.time() > timeout:
                    print("Timeout while waiting for assistant response")
                    return jsonify({"error": "Timeout waiting for assistant response"}), 500

                time.sleep(1)  # 1 saniye bekle

            messages = client.beta.threads.messages.list(
                thread_id=current_thread_id,
                order="desc",
                limit=1
            )

            if not messages.data:
                return jsonify({"error": "No response from assistant"}), 500

            assistant_response = messages.data[0].content[0].text.value

            db_message = Message(
                id=messages.data[0].id,
                thread_id=current_thread_id,
                content=assistant_response,
                role="assistant"
            )
            db.session.add(db_message)
            db.session.commit()

            return jsonify({
                'messages': [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_response}
                ]
            })

        except Exception as e:
            print(f"Error in chat: {str(e)}")
            return jsonify({"error": str(e)}), 500

    # GET isteği için parametreleri hazırla
    messages = []
    current_thread_id = None # Yeni oluşturulan thread ID atanacak

    return render_template(
        'aris.html',
        messages=messages,
        current_thread_id=current_thread_id
    )

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.username = request.form['username']
        current_user.email = request.form['email']
        
        if request.form['password']:
            current_user.password = generate_password_hash(request.form['password'])
            
        db.session.commit()
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user=current_user)

@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True,host="0.0.0.0")