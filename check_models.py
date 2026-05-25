from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
client = OpenAI()
models = sorted([m.id for m in client.models.list() if "gpt" in m.id])
print(f"\nYou have access to {len(models)} GPT models:\n")
for m in models:
    print(" ", m)
