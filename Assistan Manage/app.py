import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# OpenAI istemcisini API anahtarınızla başlatın
client = OpenAI(api_key="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")

# Asistan yönetimi için rota
@app.route('/admin/assistant', methods=['GET', 'POST'])
def manage_assistants():
    if request.method == 'POST':
        # Asistan oluştur
        instructions = request.form.get('instructions')
        name = request.form.get('name')
        model = request.form.get('model')
        vector_store_id = request.form.get('vector_store_id')

        tools = []
        if request.form.get('file_search'):
            tools.append({"type": "file_search"})
        if request.form.get('code_interpreter'):
            tools.append({"type": "code_interpreter"})

        tool_resources = {}
        if vector_store_id:
            tool_resources["file_search"] = {"vector_store_ids": [vector_store_id]}

        try:
            assistant = client.beta.assistants.create(
                instructions=instructions,
                name=name,
                model=model,
                tools=tools,
                tool_resources=tool_resources
            )
            return jsonify({'message': 'Asistan başarıyla oluşturuldu', 'assistant': assistant.model_dump()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Mevcut asistanları al
    try:
        assistants = client.beta.assistants.list()
        return render_template('assistants.html', assistants=assistants.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Asistanı güncelle
@app.route('/admin/assistant/update/<assistant_id>', methods=['POST'])
def update_assistant(assistant_id):
    instructions = request.form.get('instructions')
    name = request.form.get('name')
    model = request.form.get('model')
    vector_store_id = request.form.get('vector_store_id')

    tools = []
    if request.form.get('file_search'):
        tools.append({"type": "file_search"})
    if request.form.get('code_interpreter'):
        tools.append({"type": "code_interpreter"})

    tool_resources = {}
    if vector_store_id:
        tool_resources["file_search"] = {"vector_store_ids": [vector_store_id]}

    try:
        assistant = client.beta.assistants.update(
            assistant_id,
            instructions=instructions,
            name=name,
            model=model,
            tools=tools,
            tool_resources=tool_resources
        )
        return jsonify({'message': 'Asistan başarıyla güncellendi', 'assistant': assistant.model_dump()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Asistanı sil
@app.route('/admin/assistant/delete/<assistant_id>', methods=['POST'])
def delete_assistant(assistant_id):
    try:
        response = client.beta.assistants.delete(assistant_id)
        return jsonify({'message': 'Asistan başarıyla silindi', 'response': response.model_dump()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/admin/assistant/edit/<assistant_id>', methods=['GET', 'POST'])
def edit_assistant(assistant_id):
    if request.method == 'POST':
        # Asistanı güncelle
        instructions = request.form.get('instructions')
        name = request.form.get('name')
        model = request.form.get('model')
        vector_store_id = request.form.get('vector_store_id')

        tools = []
        if request.form.get('file_search'):
            tools.append({"type": "file_search"})
        if request.form.get('code_interpreter'):
            tools.append({"type": "code_interpreter"})

        tool_resources = {}
        if vector_store_id:
            tool_resources["file_search"] = {"vector_store_ids": [vector_store_id]}

        try:
            assistant = client.beta.assistants.update(
                assistant_id,
                instructions=instructions,
                name=name,
                model=model,
                tools=tools,
                tool_resources=tool_resources
            )
            return jsonify({'message': 'Asistan başarıyla güncellendi', 'assistant': assistant.model_dump()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        # Asistan detaylarını al
        try:
            assistant = client.beta.assistants.retrieve(assistant_id)
            return render_template('edit_assistant.html', assistant=assistant)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)