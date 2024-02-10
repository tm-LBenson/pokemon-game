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
        self.session_id = trainer_name
        self.team = []  
        self.status = 'waiting'  

    def to_dict(self):
        return {
            "trainer_name": self.trainer_name,
            "session_id": self.session_id,
            "team": [pokemon.to_dict() for pokemon in self.team] if self.team else [],
            "status": self.status
        }

game_state = {
    'trainers': {},
    'battles': {},
    'queue': Queue()
}

def match_players():
    with queue_lock:
        while game_state['queue'].qsize() >= 2:
            trainer1 = game_state['queue'].get()
            trainer2 = game_state['queue'].get()

            trainer1.status = 'in_battle'
            trainer2.status = 'in_battle'
            new_battle = Battle(trainer1, trainer2)
            
            battle_id = f"{trainer1.session_id}:{trainer2.session_id}"
            game_state['battles'][battle_id] = new_battle
            
            socketio.emit('battle_start', {'battle_id': battle_id}, room=trainer1.session_id)
            socketio.emit('battle_start', {'battle_id': battle_id}, room=trainer2.session_id)


def init_matchmaking():
    socketio.start_background_task(match_players)


init_matchmaking()

def fetch_random_pokemon(count):
    total_pokemon = 1300 
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
        self.turn = trainer1.session_id  
        self.state = 'active'  

    def to_json(self):
        return json.dumps({
            'trainer1': self.trainer1.trainer_name,
            'trainer2': self.trainer2.trainer_name,
            'turn': self.turn,
            'state': self.state,
        })
    def process_turn(self, action):
        if action['type'] == 'ability':
            ability = action['ability']
            self.apply_ability(ability, self.get_active_pokemon(), self.get_opponent_pokemon())
        elif action['type'] == 'swap':
            self.swap_pokemon(self.get_active_trainer(), action['pokemon_id'])

        self.update_battle_state()
        self.switch_turn()

    def apply_ability(self, ability, user_pokemon, target_pokemon):
        # Implement the logic to apply the selected ability's effects
        pass

    def is_battle_over(self):
        # Placeholder logic to determine if the battle is over
        # Check if all Pokémon on either team have fainted
        pass

    def get_winner(self):
        # Placeholder logic to determine the winner of the battle
        # This could simply check which trainer still has Pokémon that haven't fainted
        pass
    def apply_ability(self, ability, user_pokemon, target_pokemon):
        # Placeholder: Reduce target Pokémon HP by a fixed amount for testing
        damage = 10  #TODO update to number from the API
        target_pokemon['current_hp'] -= damage
        if target_pokemon['current_hp'] < 0:
            target_pokemon['current_hp'] = 0


    def swap_pokemon(self, trainer, pokemon_id):
        # Implement the logic to swap the current active Pokémon with another from the trainer's team
        pass

    def update_battle_state(self):
        # Check if a Pokémon has fainted, update statuses, etc.
        pass

    def switch_turn(self):
        # Switch the turn to the other trainer
        pass

@app.route('/game-state', methods=['GET'])
def get_game_state():
   # Convert trainers to a serializable format
    trainers_dict = {session_id: trainer.to_dict() for session_id, trainer in game_state["trainers"].items()}
    
    # Assuming you also need to serialize Battle objects, do similarly
    battles_dict = {}
    for battle_id, battle in game_state["battles"].items():
        battles_dict[battle_id] = {
            "trainer1": battle.trainer1.to_dict(),
            "trainer2": battle.trainer2.to_dict(),
            "turn": battle.turn,
            "state": battle.state
            # Add other necessary fields from your Battle class
        }

    return jsonify({"battles": battles_dict, "trainers": trainers_dict})


@app.route('/battle-arena', methods=['POST'])
def battle_arena():
    session_id = request.cookies.get('session')
    trainer = game_state['trainers'].get(session_id)
    
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    if trainer.status != 'in_battle':
        return jsonify({'error': 'Trainer is not in a battle'}), 400

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
    def to_dict(self):
        return {
            "name": self.name,
            "image": self.image,
            "abilities": self.abilities,
            "current_hp": self.current_hp
            # Include other fields as needed
        }
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

    session_id = trainer_name  

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
        if len(selected_pokemon_ids) != 5: 
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
