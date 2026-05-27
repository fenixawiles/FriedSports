// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', function () {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    }, 4000);
  });
});
