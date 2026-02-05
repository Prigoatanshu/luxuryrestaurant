document.addEventListener("DOMContentLoaded", () => {
  const reveals = document.querySelectorAll(".reveal");
  const parallaxItems = document.querySelectorAll("[data-parallax]");

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.2 }
  );

  reveals.forEach((item, index) => {
    item.style.transitionDelay = `${Math.min(index * 70, 350)}ms`;
    observer.observe(item);
  });

  let ticking = false;
  const onScroll = () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        const offset = window.scrollY;
        parallaxItems.forEach((item, index) => {
          const depth = (index + 1) * 0.04;
          item.style.transform = `translateY(${offset * depth}px)`;
        });
        ticking = false;
      });
      ticking = true;
    }
  };

  window.addEventListener("scroll", onScroll, { passive: true });
});
