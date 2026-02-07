(function () {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    var element = byId(id);
    if (element && typeof value === "string" && value.trim()) {
      element.textContent = value;
    }
  }

  function buildMenu(items) {
    var menuGrid = byId("menu-grid");
    if (!menuGrid) {
      return;
    }

    menuGrid.innerHTML = "";

    (items || []).forEach(function (item) {
      var card = document.createElement("article");
      card.className = "menu__card";

      var img = document.createElement("img");
      img.loading = "lazy";
      img.src = item.image || "assets/images/dish-01.jpg";
      img.alt = item.alt || item.name || "Dish";

      var content = document.createElement("div");
      content.className = "menu__content";

      var title = document.createElement("h3");
      title.textContent = item.name || "Menu Item";

      var description = document.createElement("p");
      description.textContent = item.description || "";

      var meta = document.createElement("div");
      meta.className = "menu__meta";

      var tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = item.tag || "Featured";

      var price = document.createElement("span");
      price.className = "price";
      price.textContent = item.price || "$0";

      meta.appendChild(tag);
      meta.appendChild(price);
      content.appendChild(title);
      content.appendChild(description);
      content.appendChild(meta);
      card.appendChild(img);
      card.appendChild(content);
      menuGrid.appendChild(card);
    });
  }

  function buildVideos(videos) {
    var videosGrid = byId("videos-grid");
    if (!videosGrid) {
      return;
    }

    videosGrid.innerHTML = "";

    (videos || []).forEach(function (item) {
      var card = document.createElement("div");
      card.className = "video-card";

      var video = document.createElement("video");
      video.controls = true;
      video.playsInline = true;
      video.preload = "metadata";
      if (item.poster) {
        video.poster = item.poster;
      }

      var source = document.createElement("source");
      source.src = item.video || "assets/videos/hero.mp4";
      source.type = "video/mp4";
      video.appendChild(source);

      var title = document.createElement("h3");
      title.textContent = item.title || "Inside Luxurydine";

      var description = document.createElement("p");
      description.textContent = item.description || "";

      card.appendChild(video);
      card.appendChild(title);
      card.appendChild(description);
      videosGrid.appendChild(card);
    });
  }

  function applyContent(content) {
    var brand = content.brand || {};
    var hero = content.hero || {};
    var about = content.about || {};
    var menu = content.menu || {};
    var booking = content.booking || {};
    var ordering = content.ordering || {};
    var footer = content.footer || {};

    setText("brand-name", brand.name);
    setText("topbar-email", brand.email);
    setText("topbar-address", brand.address);
    setText("topbar-phone", brand.phone);

    setText("hero-eyebrow", hero.eyebrow);
    setText("hero-title", hero.title);
    setText("hero-description", hero.description);
    setText("hero-caption", hero.caption);

    var heroVideo = byId("hero-video");
    var heroSource = byId("hero-video-source");
    if (heroVideo && hero.poster) {
      heroVideo.poster = hero.poster;
    }
    if (heroSource && hero.video) {
      heroSource.src = hero.video;
      heroVideo.load();
    }

    var heroStats = byId("hero-stats");
    if (heroStats) {
      heroStats.innerHTML = "";
      (hero.stats || []).forEach(function (stat) {
        var wrapper = document.createElement("div");
        wrapper.className = "stat";

        var value = document.createElement("span");
        value.className = "stat__value";
        value.textContent = stat.value || "";

        var label = document.createElement("span");
        label.className = "stat__label";
        label.textContent = stat.label || "";

        wrapper.appendChild(value);
        wrapper.appendChild(label);
        heroStats.appendChild(wrapper);
      });
    }

    setText("about-eyebrow", about.eyebrow);
    setText("about-title", about.title);
    setText("about-description", about.description);
    setText("about-badge", about.badge);

    var aboutImage = byId("about-image");
    if (aboutImage && about.image) {
      aboutImage.src = about.image;
    }

    setText("menu-eyebrow", menu.eyebrow);
    setText("menu-title", menu.title);

    setText("booking-title", booking.title);
    setText("booking-description", booking.description);
    setText("ordering-title", ordering.title);
    setText("ordering-description", ordering.description);

    setText("footer-brand", brand.name);
    setText("footer-brand-small", brand.name);
    setText("footer-tagline", footer.tagline);
    setText("footer-address", brand.address);
    setText("footer-phone", brand.phone);
    setText("footer-email", brand.email);
    setText("footer-social", footer.social);

    if (footer.hours && footer.hours.length > 0) {
      setText("footer-hours-1", footer.hours[0]);
    }
    if (footer.hours && footer.hours.length > 1) {
      setText("footer-hours-2", footer.hours[1]);
    }

    buildMenu(menu.items || []);
    buildVideos(content.videos || []);
  }

  function formToJson(form) {
    var formData = new FormData(form);
    var payload = {};
    formData.forEach(function (value, key) {
      payload[key] = value;
    });
    return payload;
  }

  function setFeedback(element, message, isSuccess) {
    if (!element) {
      return;
    }

    element.textContent = message;
    element.classList.remove("is-success", "is-error");
    element.classList.add(isSuccess ? "is-success" : "is-error");
  }

  async function submitForm(form, endpoint, feedbackId) {
    var feedback = byId(feedbackId);
    setFeedback(feedback, "Submitting...", true);

    try {
      var response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formToJson(form)),
      });

      var data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.message || "Request failed");
      }

      form.reset();
      setFeedback(feedback, data.message || "Submitted", true);
    } catch (error) {
      setFeedback(feedback, error.message || "Submission failed", false);
    }
  }

  async function loadContent() {
    try {
      var response = await fetch("/api/content", { method: "GET" });
      if (!response.ok) {
        throw new Error("Failed to load content");
      }

      var content = await response.json();
      applyContent(content);
    } catch (error) {
      console.error(error);
    }
  }

  var reservationForm = byId("reservation-form");
  if (reservationForm) {
    reservationForm.addEventListener("submit", function (event) {
      event.preventDefault();
      submitForm(reservationForm, "/api/reservations", "reservation-feedback");
    });
  }

  var orderForm = byId("order-form");
  if (orderForm) {
    orderForm.addEventListener("submit", function (event) {
      event.preventDefault();
      submitForm(orderForm, "/api/orders", "order-feedback");
    });
  }

  var footerYear = byId("footer-year");
  if (footerYear) {
    footerYear.textContent = String(new Date().getFullYear());
  }

  loadContent();
})();
