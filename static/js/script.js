document.addEventListener("DOMContentLoaded", () => {

  // -------- Tema oscuro/claro --------
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      document.body.style.backgroundColor = '#000000';
      document.body.style.color = '#ffffff';
      themeToggle.textContent = '☀️';
    }

    themeToggle.addEventListener('click', () => {
      const isDark = document.body.style.backgroundColor !== 'rgb(0, 0, 0)';
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
  }

  // -------- Chat interactivo --------
  // Buscar solo el formulario de chat (dentro de .chat-box)
  const chatBox = document.querySelector(".chat-box");
  const form = chatBox ? chatBox.closest("form") : null;
  const input = form ? form.querySelector("input[name='mensaje']") : null;

  if (chatBox && form && input) {
    form.addEventListener("submit", (e) => {
      e.preventDefault(); // Solo evita recarga en formulario de chat
      const userMsg = input.value.trim();
      if (!userMsg) return;

      // Mostrar mensaje del usuario
      const userDiv = document.createElement("div");
      userDiv.classList.add("mb-2");
      userDiv.innerHTML = `<span class="user">Tú:</span> ${userMsg}`;
      chatBox.appendChild(userDiv);
      chatBox.scrollTop = chatBox.scrollHeight;
      input.value = "";

      // Mostrar "typing" del bot
      const botDiv = document.createElement("div");
      botDiv.classList.add("mb-2");
      botDiv.innerHTML = `<span class="bot">Asistente:</span> <span class="typing">...</span>`;
      chatBox.appendChild(botDiv);
      chatBox.scrollTop = chatBox.scrollHeight;

      const typingSpan = botDiv.querySelector(".typing");
      const respuesta = `Esta es la respuesta simulada para: "${userMsg}"`;

      // Simular escritura letra por letra
      setTimeout(() => {
        typingSpan.textContent = "";
        let i = 0;
        const interval = setInterval(() => {
          typingSpan.textContent += respuesta[i];
          i++;
          chatBox.scrollTop = chatBox.scrollHeight;
          if (i === respuesta.length) clearInterval(interval);
        }, 50); // velocidad por letra
      }, 800); // delay inicial
    });
  }

});
