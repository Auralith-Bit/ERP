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
        const root = document.documentElement;
        if (mode === 'dark') {
            root.classList.add('dark-mode');
            root.dataset.theme = 'dark';
            button.textContent = 'Light Mode';
            localStorage.setItem(storageKey, 'dark');
        } else {
            root.classList.remove('dark-mode');
            root.dataset.theme = 'light';
            button.textContent = 'Dark Mode';
            localStorage.setItem(storageKey, 'light');
        }
    }

    button.addEventListener('click', function() {
        const nextMode = document.documentElement.classList.contains('dark-mode') ? 'light' : 'dark';
        setAdminTheme(nextMode);
    });

    button.textContent = document.documentElement.classList.contains('dark-mode') ? 'Light Mode' : 'Dark Mode';

    document.addEventListener('wheel', function(e) {
        if (e.target.type === 'number') e.preventDefault();
    }, { passive: false });
});
