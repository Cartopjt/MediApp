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

});
