from openai import AssistantEventHandler, OpenAI

client = OpenAI(api_key="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")

vector_storeid = "vs_8m5ARbkXIbITPi5xTcuNnFUx"

assistant = client.beta.assistants.create(
    name="ANAYASA BOTU",
    instructions="Türkiye Cumhuriyeti Anayasası hakkında bilgi sağlamak senin işin!",
    model="gpt-4o-mini",
    tools=[{"type": "file_search"}],
)

assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={"file_search": {"vector_store_ids": [vector_storeid]}},
)

# Upload the user provided file to OpenAI
message_file = "file-TBtWJo4YGkMiWLrNeNuQ7K"

# Create a thread and attach the file to the message
thread = client.beta.threads.create(
messages=[
  {
    "role": "user",
    "content": "Anayasanın değiştirilemez maddeleri nelerdir ?",
    # Attach the new file to the message.
    "attachments": [
      { "file_id": message_file, "tools": [{"type": "file_search"}] }
    ],
  }
]
)

# The thread now has a vector store with that file in its tool resources.
print(thread.tool_resources.file_search)

from typing_extensions import override


class EventHandler(AssistantEventHandler):
  @override
  def on_text_created(self, text) -> None:
      print(f"\nassistant > ", end="", flush=True)

  @override
  def on_tool_call_created(self, tool_call):
      print(f"\nassistant > {tool_call.type}\n", flush=True)

  @override
  def on_message_done(self, message) -> None:
      # print a citation to the file searched
      message_content = message.content[0].text
      annotations = message_content.annotations
      citations = []
      for index, annotation in enumerate(annotations):
          message_content.value = message_content.value.replace(
              annotation.text, f"[{index}]"
          )
          if file_citation := getattr(annotation, "file_citation", None):
              cited_file = client.files.retrieve(file_citation.file_id)
              citations.append(f"[{index}] {cited_file.filename}")

      print(message_content.value)
      print("\n".join(citations))


with client.beta.threads.runs.stream(
  thread_id=thread.id,
  assistant_id=assistant.id,
  instructions="Türkiye Cumhuriyeti Anayasası hakkında bilgi sağlamak senin işin!",
  event_handler=EventHandler(),
) as stream:
  stream.until_done()