document.addEventListener('DOMContentLoaded', function() {
    const storageKey = 'adminThemeMode';
    const button = document.createElement('button');
    button.id = 'adminThemeToggle';
    button.type = 'button';
    button.style.position = 'fixed';
    button.style.bottom = '18px';
    button.style.right = '18px';
    button.style.zIndex = '9999';
    button.style.border = 'none';
    button.style.background = '#1A4B8D';
    button.style.color = 'white';
    button.style.padding = '10px 14px';
    button.style.borderRadius = '999px';
    button.style.cursor = 'pointer';
    button.style.boxShadow = '0 5px 20px rgba(0,0,0,0.2)';
    document.body.appendChild(button);

    function setAdminTheme(mode) {
        const bodyClass = document.body.classList;
        if (mode === 'dark') {
            bodyClass.add('dark-mode');
            button.textContent = 'Light Mode';
            localStorage.setItem(storageKey, 'dark');
        } else {
            bodyClass.remove('dark-mode');
            button.textContent = 'Dark Mode';
            localStorage.setItem(storageKey, 'light');
        }
    }

    button.addEventListener('click', function() {
        const nextMode = document.body.classList.contains('dark-mode') ? 'light' : 'dark';
        setAdminTheme(nextMode);
    });

    setAdminTheme(localStorage.getItem(storageKey) || 'light');
});
