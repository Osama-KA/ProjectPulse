import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
# Foundry's OpenAI-compatible v1 surface: base_url ends at /openai/v1/
endpoint = os.environ["AZURE_INFERENCE_ENDPOINT"]
base_url = endpoint.split("/openai/")[0] + "/openai/v1/"
client = OpenAI(base_url=base_url, api_key=os.environ["AZURE_INFERENCE_KEY"])
resp = client.responses.create(
    model=os.environ["AZURE_INFERENCE_DEPLOYMENT"],
    input="Reply with exactly: connection works",
)
print(resp.output_text)
