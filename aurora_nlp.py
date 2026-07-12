from openai import OpenAI
import json

client = OpenAI()


def analyze_message(message):
    prompt = f"""
Extraia informações esportivas.

Retorne JSON.

Mensagem:
{message}

Formato:

{{
 "intent":"",
 "teams":[],
 "competition":"",
 "is_live":false
}}
"""

    response = client.responses.create(model="gpt-5-mini", input=prompt)

    return response.output_text


print(analyze_message("analise argentina e suiça ao vivo agora"))
