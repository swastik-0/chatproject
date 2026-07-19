(function () {
    const root = document.documentElement;
    const toggleBtn = document.getElementById('theme-toggle');
    const storageKey = 'codechat-theme';

    function applyTheme(theme) {
        root.setAttribute('data-theme', theme);
        localStorage.setItem(storageKey, theme);
    }

    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const saved = localStorage.getItem(storageKey) || (prefersDark ? 'dark' : 'light');
    applyTheme(saved);

    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const current = root.getAttribute('data-theme');
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    }
})();
