from flask import Flask, jsonify, request, session
import random
from queue import Queue
import requests
app = Flask(__name__)
app.secret_key = 'your_secret_key'  
class Trainer:
    def __init__(self, trainer_name, session_id):
        self.trainer_name = trainer_name
        self.session_id = session_id
        self.team = []  # List to store selected Pokémon
        self.status = 'waiting'  # Can be 'waiting', 'in_battle', or 'observing'

# A dictionary to maintain the state of the game
game_state = {
    'trainers': {},  # Stores Trainer objects by session_id
    'battles': {},  # Stores ongoing battles
    'queue': Queue()  # Queue for users waiting to play
}
def fetch_random_pokemon(count):
    # Assume there's a known number of Pokémon.
    # Use the latest number from the PokeAPI documentation or your own data.
    total_pokemon = 1300  # Replace with the current total number of Pokémon
    random_ids = random.sample(range(1, total_pokemon + 1), count)
    pokemon_data = []
    
    for pokemon_id in random_ids:
        pokemon_info = Pokemon.fetch_pokemon_data(pokemon_id)
        if pokemon_info:
            pokemon_data.append(pokemon_info)
        else:
            # If a Pokemon is not found, handle it appropriately, maybe log the error
            pass  # Or continue, or break, depending on your error handling strategy

    return pokemon_data

# A class to represent a Pokemon
class Pokemon:
    def __init__(self, name, image, abilities, hp):
        self.name = name
        self.image = image
        self.abilities = abilities
        self.current_hp = hp
        # Add more attributes as needed

    # Method to fetch data from PokeAPI
    @staticmethod
    def fetch_pokemon_data(pokemon_id):
        try:
            response = requests.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}')
            response.raise_for_status()  # Will raise an exception for HTTP errors
            data = response.json()

            # Extracting the necessary data
            name = data['name']
            image = data['sprites']['front_default']  # You can choose other images too
            abilities = [ability['ability']['name'] for ability in data['abilities']]
            hp = next(stat['base_stat'] for stat in data['stats'] if stat['stat']['name'] == 'hp')

            return {
                'name': name,
                'image': image,
                'abilities': abilities,
                'hp': hp
            }
        except requests.RequestException as e:
            print(f"An error occurred while fetching data: {e}")
            return None
        
# Routes for your game
@app.route('/choose-trainer', methods=['POST'])
def choose_trainer():
    trainer_name = request.json.get('trainer_name')
    if not trainer_name:
        return jsonify({'error': 'Trainer name is required'}), 400

    session_id = request.cookies.get('session')  # Or however you are managing sessions

    if session_id in game_state['trainers']:
        return jsonify({'error': 'This session already has a trainer'}), 400

    if trainer_name in (trainer.trainer_name for trainer in game_state['trainers'].values()):
        return jsonify({'error': 'Trainer name is already taken'}), 400

    # Create a new trainer
    new_trainer = Trainer(trainer_name, session_id)
    game_state['trainers'][session_id] = new_trainer

    # Optionally, add the trainer to the queue
    game_state['queue'].put(new_trainer)

    return jsonify({'message': 'Trainer created successfully', 'trainer_name': trainer_name}), 200


@app.route('/select-pokemon', methods=['GET', 'POST'])
def select_pokemon():
    session_id = request.cookies.get('session')
    if request.method == 'GET':
        # Fetch 20 random Pokémon from PokeAPI
        pokemon_list = fetch_random_pokemon(20)
        session['available_pokemon'] = pokemon_list
        return jsonify(pokemon_list)
    elif request.method == 'POST':
        # User submits their selected Pokémon
        selected_pokemon_ids = request.json.get('selected_pokemon')
        if not selected_pokemon_ids:
            return jsonify({'error': 'No Pokémon selected'}), 400
        if len(selected_pokemon_ids) != 5:  # Assuming each trainer selects 5 Pokémon
            return jsonify({'error': 'Incorrect number of Pokémon selected'}), 400

        trainer = game_state['trainers'].get(session_id)
        if not trainer:
            return jsonify({'error': 'Trainer not found'}), 404
        
        for pokemon_id in selected_pokemon_ids:
            pokemon_data = Pokemon.fetch_pokemon_data(pokemon_id)
            if pokemon_data:
                trainer.team.append(pokemon_data)
            else:
                # Handle the error if Pokémon data is not found
                return jsonify({'error': f'Pokémon with id {pokemon_id} not found'}), 404
        
        return jsonify({'message': 'Pokémon selected successfully'}), 200


@app.route('/battle-arena')
def battle_arena():
    # Logic for the battle arena
    pass

# Add more routes and logic as needed

if __name__ == '__main__':
    app.run(debug=True)
