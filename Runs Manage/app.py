import os
import time
import openai

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from openai import OpenAI
from dotenv import load_dotenv

# Ortam değişkenlerini yükle
load_dotenv()

app = Flask(__name__)

# OpenAI istemcisini başlat
client = OpenAI(api_key="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")

# Asistan ve thread IDs (Bunları veritabanı veya diğer kalıcı depolama alanlarında saklayabilirsiniz)
assistant_id = None  # Genel kapsamda başlatıldı
thread_id = None

try:
    # Dosyaları yükle
    file1 = client.files.create(
        file=open("pdf1.pdf", "rb"),
        purpose="assistants"
    )

    file2 = client.files.create(
        file=open("pdf2.pdf", "rb"),
        purpose="assistants"
    )
    # Asistanı oluştur
    assistant = client.beta.assistants.create(
        name="Sohbet Asistanı",
        instructions="Kullanıcının sorularını yanıtlamak için bilgileri kullanın.",
        model="gpt-4o-mini",
        tools=[{"type": "retrieval"}],
        file_ids=[file1.id, file2.id]
    )
    assistant_id = assistant.id
    print(f"Asistan oluşturuldu: {assistant_id}")

    # Thread oluştur
    thread = client.beta.threads.create()
    thread_id = thread.id
    print(f"Thread oluşturuldu: {thread_id}")

except openai.RateLimitError as e:
    print(f"Hata: {e}")

except Exception as e:
    print(f"Bilinmeyen bir hata oluştu: {e}")

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/ask", methods=["POST"])
def ask():
    global thread_id

    if not thread_id:
        return jsonify({"error": "Thread başlatılmamış."}), 500

    try:
        message_content = request.form["message"]

        # Kullanıcı mesajını thread'e ekle
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message_content
        )

        # Mesajı çalıştırmak için yeni bir çalıştırma oluştur
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        def generate(run_id):
            global thread_id  # `thread_id` değişkenini değiştireceğinizi belirtin

            while True:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run_id
                )

                if run_status.status == "completed":
                    messages = client.beta.threads.messages.list(thread_id=thread_id)
                    assistant_messages = [
                        msg for msg in messages if msg.role == "assistant"
                    ]

                    for msg in assistant_messages:
                        for content in msg.content:
                            if content.type == "text":
                                yield f"data: {content.text.value}\n\n"
                    break
                elif run_status.status == "failed":
                    yield "data: Akış hatası: Çalıştırma başarısız oldu.\n\n"
                    break
                else:
                    time.sleep(1)

        return Response(stream_with_context(generate(run.id)), mimetype="text/event-stream")

    except Exception as e:
        print(f"Hata: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/admin/runs")
def admin_runs():
    try:
        if thread_id:
            # Thread için tüm çalıştırmaları al
            runs = client.beta.threads.runs.list(thread_id=thread_id)

            # Her çalıştırma için adımları al
            runs_with_steps = []
            for run in runs.data:
                steps = client.beta.threads.runs.steps.list(
                    thread_id=thread_id,
                    run_id=run.id
                )
                runs_with_steps.append({
                    "run": run,
                    "steps": steps.data
                })

            # Tüm mesajları al
            messages = client.beta.threads.messages.list(thread_id=thread_id).data

            return render_template("admin.html", runs=runs_with_steps, messages=messages, thread_id=thread_id)
        else:
            return "Thread başlatılmamış."

    except Exception as e:
        print(f"Hata: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/delete_run/<run_id>", methods=["POST"])
def delete_run(run_id):
    try:
        if thread_id:
            response = client.beta.threads.runs.cancel(
                thread_id=thread_id,
                run_id=run_id
            )
            return jsonify({"message": "Çalıştırma silindi", "status": response.status})
        else:
            return jsonify({"error": "Thread başlatılmamış."}), 400
    except Exception as e:
        print(f"Hata: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/delete_message/<message_id>", methods=["POST"])
def delete_message(message_id):
    try:
        if thread_id:
            response = client.beta.threads.messages.delete(
                thread_id=thread_id,
                message_id=message_id
            )
            return jsonify({"message": "Mesaj silindi", "status": "silindi"})
        else:
            return jsonify({"error": "Thread başlatılmamış."}), 400
    except Exception as e:
        print(f"Hata: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)