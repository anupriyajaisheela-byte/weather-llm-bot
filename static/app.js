const chat = document.getElementById('chat');
const form = document.getElementById('form');
const promptEl = document.getElementById('prompt');
const locationEl = document.getElementById('location');

function appendMessage(text, who = 'bot') {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg ' + (who === 'user' ? 'user' : 'bot');
    const bubble = document.createElement('div');
    bubble.className = 'bubble ' + (who === 'user' ? 'user' : 'bot');
    bubble.innerText = text;
    wrapper.appendChild(bubble);
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = promptEl.value.trim();
    const loc = locationEl.value.trim();

    if (!text) return;

    appendMessage(text, 'user');
    promptEl.value = '';
    
    // Add temporary loader
    appendMessage('...', 'bot');
    const msgs = chat.querySelectorAll('.msg.bot');
    const lastLoader = msgs[msgs.length - 1];

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, location: loc || null })
        });

        const j = await res.json();
        
        // Remove the loader before showing real response
        if (lastLoader) lastLoader.remove();

        // Main Bot Response
        appendMessage(j.reply || "I'm having trouble thinking right now.", 'bot');

        // Weather Metadata (Only show if data actually exists)
       console.log(j.weather);

if (j.weather && j.weather.location_name) {
    const info = `(Weather used: ${j.weather.location_name}, ${j.weather.weather_summary})`;
    appendMessage(info, 'bot');
} else if (j.weather) {
    // This checks if temperature exists; if not, it just says "Live data synchronized"
    const statusText = j.weather.temperature 
        ? `${j.weather.temperature}°C data synchronized` 
        : "Live weather data synchronized";
    
    appendMessage(`(Status: ${statusText})`, 'bot');
}
    } catch (err) {
        if (lastLoader) lastLoader.remove();
        console.error("Fetch error:", err);
        appendMessage('Connection lost. Please check your internet or server logs.', 'bot');
    }
});

// Welcome message
appendMessage('Hello — ask me anything about the weather. Provide a location if you want local details.', 'bot');