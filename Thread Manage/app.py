import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# OpenAI istemcisini API anahtarınızla başlatın
client = OpenAI(api_key="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") # YOUR_API_KEY'i kendi api anahtarınızla değiştirin.

# Mevcut thread'leri saklamak için geçici bir sözlük (gerçek bir uygulamada veritabanı kullanmalısınız)
threads_store = {}

@app.route('/admin/threads')
def index():
    """Thread yönetim sayfasını gösterir."""
    return render_template('index.html')

@app.route('/api/threads', methods=['POST'])
def create_thread():
    """Yeni bir thread oluşturur."""
    data = request.get_json()
    messages = data.get('messages', [])
    
    # Thread oluştur
    try:
        thread = client.beta.threads.create(messages=messages)
        threads_store[thread.id] = thread  # Thread'i yerel depoya kaydet
        return jsonify({'thread_id': thread.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/threads/<thread_id>/messages', methods=['POST'])
def add_message_to_thread(thread_id):
    """Belirli bir thread'e mesaj ekler."""
    data = request.get_json()
    message_content = data.get('message')
    
    # Mesaj oluştur
    try:
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message_content
        )
        return jsonify({'message_id': message.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/threads/<thread_id>', methods=['PUT'])
def update_thread(thread_id):
    """Mevcut bir thread'i günceller."""
    data = request.get_json()
    metadata = data.get('metadata', {})

    # Thread'i güncelle
    try:
        updated_thread = client.beta.threads.update(thread_id, metadata=metadata)
        threads_store[thread_id] = updated_thread  # Güncellenmiş thread'i yerel depoya kaydet
        return jsonify({'message': 'Thread güncellendi', 'thread_id': updated_thread.id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/threads/<thread_id>', methods=['DELETE'])
def delete_thread(thread_id):
    """Belirli bir thread'i siler."""
    # Thread'i sil
    try:
        response = client.beta.threads.delete(thread_id)
        if thread_id in threads_store:
            del threads_store[thread_id]  # Thread'i yerel depodan sil
        return jsonify({'message': 'Thread silindi', 'status': response.deleted}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/threads', methods=['GET'])
def list_threads():
    """Tüm thread'leri listeler."""
    # Yerel depodan thread'leri al
    thread_list = [{'thread_id': thread_id, 'metadata': thread.metadata} for thread_id, thread in threads_store.items()]
    return jsonify(thread_list), 200

if __name__ == '__main__':
    app.run(debug=True)