const chat = document.getElementById('chat');
const form = document.getElementById('form');
const promptEl = document.getElementById('prompt');
const locationEl = document.getElementById('location');

function appendMessage(text, who='bot'){
  const wrapper = document.createElement('div');
  wrapper.className = 'msg ' + (who==='user'?'user':'bot');
  const bubble = document.createElement('div');
  bubble.className = 'bubble ' + (who==='user'?'user':'bot');
  bubble.innerText = text;
  wrapper.appendChild(bubble);
  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;
}

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const text = promptEl.value.trim();
  const loc = locationEl.value.trim();
  if(!text) return;
  appendMessage(text,'user');
  promptEl.value = '';
  appendMessage('...', 'bot');
  try{
    const res = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message:text, location: loc || null})
    });
    const j = await res.json();
    // remove the last '...' loader
    const last = chat.querySelectorAll('.msg.bot');
    if(last && last.length) last[last.length-1].remove();
    if(j.weather && !j.weather.get){
      // show LLM reply
    }
    appendMessage(j.reply || 'Sorry, no reply from server', 'bot');
    if(j.weather){
      appendMessage(`(Weather data used: ${j.weather.location_name || 'n/a'}, ${j.weather.weather_summary || ''})`, 'bot');
    }
  }catch(err){
    console.error(err);
    const last = chat.querySelectorAll('.msg.bot');
    if(last && last.length) last[last.length-1].remove();
    appendMessage('Network error communicating with server.', 'bot');
  }
});

// Small welcome message
appendMessage('Hello — ask me anything about the weather. Provide a location if you want local details.','bot');
