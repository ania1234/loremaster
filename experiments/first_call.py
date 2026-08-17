from dotenv import load_dotenv
from litellm import completion

load_dotenv()          # reads .env and puts the key into the environment
temperature = 1
for i in range(0, 5):
    response = completion(
        model="anthropic/claude-sonnet-4-5",
        messages=[
            {"role": "system", "content": "You are an rpg expert and enthusiast."},
            {"role": "user",   "content": "In two sentences: what is a tabletop RPG?"},
        ],
        temperature=temperature,
    )
    print(f"Temperature {temperature}, try {i}")
    print(response.choices[0].message.content)
    print("---")