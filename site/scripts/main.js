const navToggle = document.querySelector('.nav__toggle');
const navLinks = document.querySelector('.nav__links');
const body = document.body;

if (navToggle) {
  navToggle.addEventListener('click', () => {
    body.classList.toggle('nav-open');
    const expanded = body.classList.contains('nav-open');
    navToggle.setAttribute('aria-expanded', expanded);
  });
}

if (navLinks) {
  navLinks.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      body.classList.remove('nav-open');
      navToggle?.setAttribute('aria-expanded', 'false');
    });
  });
}

const revealItems = document.querySelectorAll('[data-reveal]');
if ('IntersectionObserver' in window) {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          revealObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add('is-visible'));
}

const year = document.querySelector('[data-year]');
if (year) {
  year.textContent = new Date().getFullYear();
}
