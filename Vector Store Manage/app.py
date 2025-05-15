import os
import tempfile
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_secret_key")  # Set a secret key for Flask sessions

# OpenAI client initialization
client = OpenAI(api_key="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")

@app.route('/admin/database', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Create a new vector store
        if 'create_vector_store' in request.form:
            vector_store_name = request.form.get('vector_store_name')
            if vector_store_name:
                try:
                    vector_store = client.beta.vector_stores.create(name=vector_store_name)
                    flash(f"Vector store '{vector_store_name}' created successfully!", "success")
                    return redirect(url_for('index'))
                except Exception as e:
                    flash(f"Error creating vector store: {e}", "error")
            else:
                flash("Vector store name is required!", "error")

        # Upload a file to a vector store
        elif 'upload_file' in request.form:
            vector_store_id = request.form.get('vector_store_id')
            file = request.files.get('file')
            if vector_store_id and file:
                try:
                    # Dosya adını güvenli hale getirin ve uzantısını koruyun
                    filename = secure_filename(file.filename)

                    # Geçici bir dosya oluşturun
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                        file.save(temp_file.name)
                        temp_file_path = temp_file.name

                    # Geçici dosyayı OpenAI'ye yükleyin
                    with open(temp_file_path, "rb") as temp_file:
                        # Girinti eklendi
                        openai_file = client.files.create(file=temp_file, purpose="assistants")

                        # Dosyayı vektör deposuna ekleyin
                        vector_store_file = client.beta.vector_stores.files.create(
                            vector_store_id=vector_store_id,
                            file_id=openai_file.id
                        )
                        flash(f"File uploaded and attached to vector store '{vector_store_id}'!", "success")

                    # Geçici dosyayı silin
                    os.unlink(temp_file_path)

                    return redirect(url_for('index', vector_store_id=vector_store_id))
                except Exception as e:
                    flash(f"Error uploading file: {e}", "error")
            else:
                flash("Vector store ID and file are required!", "error")


    # GET request or other cases: list vector stores
    try:
        vector_stores = client.beta.vector_stores.list().data
        print("DEBUG: All Vector Stores from API:", vector_stores) # Konsola yazdır
        selected_vector_store_id = request.args.get('vector_store_id')
        files = []
        if selected_vector_store_id:
            files = client.beta.vector_stores.files.list(vector_store_id=selected_vector_store_id).data

        return render_template('index.html', vector_stores=vector_stores, selected_vector_store_id=selected_vector_store_id, files=files)
    except Exception as e:
        flash(f"Error: {e}", "error")
        return render_template('index.html', vector_stores=[], selected_vector_store_id=None, files=[])
    
@app.route('/admin/database/delete_file', methods=['POST'])
def delete_file():
    vector_store_id = request.form.get('vector_store_id')
    file_id = request.form.get('file_id')

    if not vector_store_id or not file_id:
        return jsonify({'status': 'error', 'message': 'Vector Store ID and File ID are required!'}), 400

    try:
        # Delete the file association from the vector store
        client.beta.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)

        # Optionally, delete the file from OpenAI's storage as well
        # client.files.delete(file_id=file_id)

        return jsonify({'status': 'success', 'message': 'File deleted successfully!'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error deleting file: {e}'}), 500

@app.route('/admin/database/delete_vector_store', methods=['POST'])
def delete_vector_store():
    vector_store_id = request.form.get('vector_store_id')

    if not vector_store_id:
        return jsonify({'status': 'error', 'message': 'Vector Store ID is required!'}), 400

    try:
        client.beta.vector_stores.delete(vector_store_id=vector_store_id)
        flash(f"Vector store '{vector_store_id}' deleted successfully!", "success")
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error deleting vector store: {e}", "error")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)