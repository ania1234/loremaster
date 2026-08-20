from dotenv import load_dotenv
from litellm import completion
from app.config import settings

load_dotenv()          # reads .env and puts the key into the environment

for i in range(0, 1):
    response = completion(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": "You are an rpg expert and enthusiast."},
            {"role": "user",   "content": "In two sentences: what is a tabletop RPG?"},
        ],
        temperature=settings.temperature
    )
    print(f"Temperature {settings.temperature}, try {i}")
    print(response.choices[0].message.content)
    print("---")