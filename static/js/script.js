document.addEventListener("DOMContentLoaded", () => {

  // Toggle tema oscuro/claro
  let themeToggle = document.getElementById('themeToggle');
if (!themeToggle) {
  themeToggle = document.createElement('button');
  themeToggle.id = 'themeToggle';
  themeToggle.textContent = '🌙';
  themeToggle.style.position = 'fixed';
  themeToggle.style.top = '10px';
  themeToggle.style.right = '10px';
  themeToggle.style.background = 'none';
  themeToggle.style.border = 'none';
  themeToggle.style.fontSize = '1.2rem';
  themeToggle.style.cursor = 'pointer';
  themeToggle.style.zIndex = '9999';
  document.body.appendChild(themeToggle);
}

// Recuperar tema guardado
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
  document.body.style.backgroundColor = '#000000';
  document.body.style.color = '#ffffff';
  themeToggle.textContent = '☀️';
}

// Alternar tema
themeToggle.addEventListener('click', () => {
  const isDark = document.body.style.backgroundColor !== 'rgb(0, 0, 0)'; // negro
  if (isDark) {
    document.body.style.backgroundColor = '#000000';
    document.body.style.color = '#ffffff';
    themeToggle.textContent = '☀️';
    localStorage.setItem('theme', 'dark');
  } else {
    document.body.style.backgroundColor = '';
    document.body.style.color = '';
    themeToggle.textContent = '🌙';
    localStorage.setItem('theme', 'light');
  }
});

  // Previsualización de imagen subida (index)
  const fileInputs = document.querySelectorAll('input[type="file"]');
  fileInputs.forEach(input => {
    input.addEventListener('change', function () {
      const file = this.files[0];
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) { // 5MB
        alert('Archivo demasiado grande (máx 5MB)');
        this.value = '';
        return;
      }
      console.log('Archivo listo para subir:', file.name);
    });
  });

  // Chat: Enter para enviar
  const chatForm = document.querySelector('form[method="POST"].d-flex');
  if (chatForm) {
    chatForm.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.submit();
      }
    });
  }

  // Simular "bot está escribiendo" (chat)
  const chatBox = document.querySelector('.chat-box');
  if (chatBox && chatForm) {
    chatForm.addEventListener('submit', e => {
      e.preventDefault();

      const userInput = chatForm.querySelector('input[name="mensaje"]');
      const userMsg = userInput.value.trim();
      if (!userMsg) return;

      const divUser = document.createElement('div');
      divUser.className = 'mb-2';
      divUser.innerHTML = `<span class="user">Tú:</span> ${userMsg}`;
      chatBox.appendChild(divUser);

      userInput.value = '';

      const typingDiv = document.createElement('div');
      typingDiv.className = 'mb-2';
      typingDiv.innerHTML = `<span class="bot">Asistente:</span> <em>Escribiendo...</em>`;
      chatBox.appendChild(typingDiv);
      chatBox.scrollTop = chatBox.scrollHeight;

      setTimeout(() => {
        typingDiv.innerHTML = `<span class="bot">Asistente:</span> Esta es la respuesta simulada a "${userMsg}".`;
        chatBox.scrollTop = chatBox.scrollHeight;
      }, 1000 + Math.random() * 1000);
    });
  }

});
