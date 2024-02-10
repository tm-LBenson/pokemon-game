from flask import Flask, jsonify, request, session
import random
from threading import Lock
from queue import Queue
import requests
import json
from flask_socketio import SocketIO, emit
app = Flask(__name__)
socketio = SocketIO(app)
app.secret_key = 'your_secret_key'  
queue_lock = Lock()
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

def match_players():
    with queue_lock:
        while game_state['queue'].qsize() >= 2:
            trainer1 = game_state['queue'].get()
            trainer2 = game_state['queue'].get()

            # Set up the battle
            trainer1.status = 'in_battle'
            trainer2.status = 'in_battle'
            new_battle = Battle(trainer1, trainer2)
            
            # Add the battle to the game state
            battle_id = f"{trainer1.session_id}:{trainer2.session_id}"
            game_state['battles'][battle_id] = new_battle
            
            # Send battle start event to both players
            socketio.emit('battle_start', {'battle_id': battle_id}, room=trainer1.session_id)
            socketio.emit('battle_start', {'battle_id': battle_id}, room=trainer2.session_id)

# Initialize the match making periodically
def init_matchmaking():
    socketio.start_background_task(match_players)

# Call this function somewhere in your setup to start the matchmaking process
init_matchmaking()

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
class Battle:
    def __init__(self, trainer1, trainer2):
        self.trainer1 = trainer1
        self.trainer2 = trainer2
        self.turn = trainer1.session_id  # Start with trainer1's turn
        self.state = 'active'  # Can be 'active', 'finished'

    def to_json(self):
        # Convert the current state of the battle to JSON
        return json.dumps({
            'trainer1': self.trainer1.trainer_name,
            'trainer2': self.trainer2.trainer_name,
            'turn': self.turn,
            'state': self.state,
        })
    def process_turn(self, action):
        # Placeholder logic to process a turn
        # You will need to replace this with actual game logic
        # 'action' parameter is a dict with details about what the player wants to do
        pass
@app.route('/battle-arena', methods=['POST'])
def battle_arena():
    session_id = request.cookies.get('session')
    trainer = game_state['trainers'].get(session_id)
    
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    if trainer.status != 'in_battle':
        return jsonify({'error': 'Trainer is not in a battle'}), 400

    # Find the battle instance
    battle = next((b for b in game_state['battles'].values() if session_id in [b.trainer1.session_id, b.trainer2.session_id]), None)

    if not battle:
        return jsonify({'error': 'Battle not found'}), 404

    if session_id == battle.turn:

        battle.turn = battle.trainer1.session_id if session_id == battle.trainer2.session_id else battle.trainer2.session_id
        socketio.emit('battle_update', battle.to_json(), room=battle.trainer1.session_id)
        socketio.emit('battle_update', battle.to_json(), room=battle.trainer2.session_id)
        return jsonify({'message': 'Turn completed'}), 200
    else:
        return jsonify({'error': 'Not your turn'}), 403

class Pokemon:
    def __init__(self, name, image, abilities, hp):
        self.name = name
        self.image = image
        self.abilities = abilities
        self.current_hp = hp

    @staticmethod
    def fetch_pokemon_data(pokemon_id):
        try:
            response = requests.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}')
            response.raise_for_status()  # Will raise an exception for HTTP errors
            data = response.json()

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

    new_trainer = Trainer(trainer_name, session_id)
    game_state['trainers'][session_id] = new_trainer

    game_state['queue'].put(new_trainer)

    return jsonify({'message': 'Trainer created successfully', 'trainer_name': trainer_name}), 200


@app.route('/select-pokemon', methods=['GET', 'POST'])
def select_pokemon():
    session_id = request.cookies.get('session')
    if request.method == 'GET':

        pokemon_list = fetch_random_pokemon(20)
        session['available_pokemon'] = pokemon_list
        return jsonify(pokemon_list)
    elif request.method == 'POST':

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

                return jsonify({'error': f'Pokémon with id {pokemon_id} not found'}), 404
        
        return jsonify({'message': 'Pokémon selected successfully'}), 200




if __name__ == '__main__':
    app.run(debug=True)
