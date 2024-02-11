// Connect to the WebSocket server
const socket = io.connect(
  `${location.protocol}//${document.domain}:${location.port}`
);

socket.on('connect', () => {
  console.log('Connected to WebSocket');
});

const sendMessage = () => {
  const messageInput = document.getElementById('chat-input');
  const trainerElement = document.getElementById('trainer-name-display');
  const trainerName = trainerElement.getAttribute('data-trainer-name');
  if (!trainerName) return alert('You need a name'); //TODO ADD BETTER LOGIC HERE FOR WHEN NO NAME
  const message = messageInput.value;
  if (message.trim()) {
    socket.emit('send_message', { username: trainerName, message });
    messageInput.value = '';
  }
};

// Listen for chat messages to display
socket.on('receive_message', (data) => {
  const chatMessages = document.getElementById('chat-messages');
  const messageElement = document.createElement('div');
  messageElement.innerHTML = `
    <div>
      <strong>${data.username}</strong>: ${data.message}
    </div>`;
  chatMessages.appendChild(messageElement);
});

// Listen for battle updates to display
socket.on('battle_update', (data) => {
  const battleStatus = document.getElementById('battle-status');
  // Example update - you need to adapt this based on how `data` structure is defined
  battleStatus.textContent = `It's ${data.turn}'s turn. State: ${data.state}`;
  // You can extend this logic to update the battle status, players' health, etc., dynamically.
});

// Example function to handle form submission or button click for sending messages
document.getElementById('send-button').addEventListener('click', sendMessage);
