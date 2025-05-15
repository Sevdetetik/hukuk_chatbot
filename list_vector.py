from openai import OpenAI

client = OpenAI(api_key="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")

# Tüm vektör store'larınızı listeleyin
asistan = client.beta.assistants.list(limit=100)  # Gerekirse limiti artırın

for ass in asistan.data:
    # Her bir vektör store'u silin
    try:
        deleted_vector_store = client.beta.assistants.delete(ass.id)
        print(f"Deleted asistan : {deleted_vector_store.id}")  # Sadece ID'yi yazdır
    except Exception as e:
        print(f"Error deleting asistan {ass.id}: {e}")