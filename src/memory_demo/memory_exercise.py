import asyncio
import uuid
import typer
import logging
from memory_demo.memory_demo import process_user_input

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()

QUESTIONS = [
    "Hi there! My name is Alice and I love drinking green tea.",
    "What is my name and what do I like to drink?",
    "I also enjoy hiking in the mountains during summer.",
    "Can you remember my hobbies and my favorite drink?",
    "I'm planning a trip to the Swiss Alps. Any suggestions based on my interests?",
    "Actually, I'm thinking of staying in Zermatt for a few days.",
    "Do you remember where I said I'm going in the Alps?",
    "I also really like photography, especially capturing mountain landscapes.",
    "What kind of scenery did I say I like to photograph?",
    "I'm a vegetarian, so I'll need some good food options there.",
    "Can you suggest some traditional Swiss vegetarian dishes?",
    "I prefer traveling by train because I enjoy the scenic routes.",
    "Why do I prefer taking the train instead of flying or driving?",
    "I'm also interested in learning about the local history of the region.",
    "Besides hiking and photography, what else am I interested in for this trip?",
    "I usually wake up early to start my hikes at dawn.",
    "What time of day do I like to start my activities?",
    "I'm bringing my Leica camera for this trip.",
    "Do you remember which brand of camera I use?",
    "I also love the sound of cowbells in the mountain pastures.",
    "What specific sound do I enjoy hearing in the mountains?",
    "I've been to the Italian Dolomites before, and I loved the food there too.",
    "Which other mountain range have I visited previously?",
    "I'm a bit worried about the altitude, any tips for that?",
    "Given my interest in hiking and photography, which peak should I focus on?",
    "I also enjoy reading mystery novels in the evenings.",
    "What do I like to do after a long day of hiking?",
    "My favorite author is Agatha Christie.",
    "Who is my favorite writer for those evening reads?",
    "I'm allergic to peanuts, so I have to be careful with snacks.",
    "Is there any food I should avoid due to my allergies?",
    "I speak a little bit of German, which might help in Zermatt.",
    "What language did I mention I can speak some of?",
    "I'm planning to stay for two weeks in total.",
    "How long is my planned trip to Switzerland?",
    "I want to see the Matterhorn, of course.",
    "Which iconic mountain am I most excited to see?",
    "I usually wear a sun hat because I have sensitive skin.",
    "Why do I wear a hat when I'm outside?",
    "I'm also looking for a good pair of waterproof hiking boots.",
    "What kind of gear am I currently looking to buy?",
    "I prefer small, boutique hotels over large resorts.",
    "What are my preferences when it comes to accommodation?",
    "I'm thinking of visiting in July.",
    "Which month did I pick for my mountain adventure?",
    "I love the smell of pine trees in the morning air.",
    "What scent do I associate with the mountains?",
    "I'm also a fan of classical music, especially Vivaldi.",
    "Who is my favorite composer for relaxing?",
    "I'm hoping to see some edelweiss flowers if I'm lucky.",
    "What specific flower am I hoping to find on the trails?",
    "I'm actually a bit of a night owl, despite starting hikes early.",
    "What did I say about my sleeping habits?",
    "I've decided to bring some dark chocolate for energy.",
    "What kind of snack am I bringing for the trail?",
    "I'm also planning to visit the local cheese dairies.",
    "What food production process am I interested in seeing?",
    "I've never tried fondue before, is it worth it?",
    "What's that traditional cheese dish I'm curious about?",
    "I'm traveling alone for this trip, any safety tips?",
    "Who else is coming with me on this adventure?",
    "I prefer to use a paper map sometimes, it's more tactile.",
    "Why do I occasionally use paper maps?",
    "I also enjoy watercolor painting, might bring my set.",
    "What artistic hobby might I do on my trip?",
    "My birthday is in August, so this is a pre-birthday trip.",
    "When is my birthday and why am I traveling now?",
    "I'm also interested in Alpine folklore and legends.",
    "What kind of stories do I want to learn about?",
    "I usually drink sparkling water during meals.",
    "What is my preferred type of water?",
    "I'm planning to take the Glacier Express.",
    "Which famous train route am I going to experience?",
    "I'm a bit of a minimalist when it comes to packing.",
    "How would I describe my packing style?",
    "I also enjoy birdwatching, especially looking for eagles.",
    "What kind of birds am I hoping to spot?",
    "I'm allergic to pollen too, so I hope it's okay in July.",
    "What's my other allergy besides peanuts?",
    "I prefer silk liners for my sleeping bag.",
    "What material do I like for my sleeping bag liner?",
    "I'm also interested in sustainable tourism.",
    "What kind of travel philosophy do I support?",
    "I usually wear merino wool socks for hiking.",
    "What material are my hiking socks made of?",
    "I'm also a fan of architecture, especially traditional chalets.",
    "What type of buildings do I find particularly interesting?",
    "I'm thinking of writing a travel blog about this.",
    "How am I planning to document my journey online?",
    "I'm also interested in geology and how these mountains formed.",
    "What scientific subject am I curious about?",
    "I usually carry a small first-aid kit with me.",
    "What safety item do I always have in my backpack?",
    "I'm also a fan of yoga, it helps with my flexibility.",
    "What exercise do I do to stay flexible for hiking?",
    "I'm hoping to see the sunrise from a mountain hut.",
    "What's one of my goals involving a mountain hut?",
    "I'm also interested in the flora and fauna of the region.",
    "What aspects of nature am I keen to observe?",
    "I usually take a lot of notes in my travel journal.",
    "Where do I record my thoughts and observations?"
]

async def run_exercise(user_count: int, question_count: int):
    """
    Iterates over a list of user IDs and processes a list of messages per user.
    """
    questions_to_ask = QUESTIONS[:question_count]
    for i in range(1, user_count + 1):
        user_id = f"user{i}"
        session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
        
        typer.echo(f"\n--- Processing for {user_id} (Session: {session_id}) ---")
        
        for question in questions_to_ask:
            typer.echo(f"User: {question}")
            response = await process_user_input(question, session_id, user_id)
            typer.echo(f"Assistant: {response}")
            typer.echo("-" * 20)

@app.command()
def main(
    users: int = typer.Option(1, help="Number of users to process"),
    questions: int = typer.Option(len(QUESTIONS), help="Number of questions to ask per user")
):
    typer.echo(f"Running Memory Exercise with {users} users and {questions} questions each")
    if questions > len(QUESTIONS):
        typer.echo(f"Error: questions parameter ({questions}) cannot exceed total questions available ({len(QUESTIONS)})")
        raise typer.Exit(code=1)
    if questions < 1:
        typer.echo("Error: questions parameter must be at least 1")
        raise typer.Exit(code=1)
    asyncio.run(run_exercise(users, questions))

if __name__ == "__main__":
    app()
