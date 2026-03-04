// Optional: Add interactivity, e.g., card click full-screen effect
document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('click', () => {
        card.classList.toggle('fullscreen');
    });
});