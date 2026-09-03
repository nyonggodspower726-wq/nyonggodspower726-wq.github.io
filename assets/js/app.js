document.addEventListener("DOMContentLoaded", () => {
  /* =========================================================
     AI NEWS FACTORY — MAIN SITE CONTROLLER
     Version: 1.0.0
     ========================================================= */

  "use strict";

  /* ---------------------------------------------------------
     1. CURRENT DATE
     --------------------------------------------------------- */

  const dateElements = document.querySelectorAll("[data-current-date]");

  if (dateElements.length) {
    const now = new Date();

    const formattedDate = now.toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric"
    });

    dateElements.forEach((element) => {
      element.textContent = formattedDate;
    });
  }

  /* ---------------------------------------------------------
     2. THEME SYSTEM
     --------------------------------------------------------- */

  const themeButton = document.querySelector(
    "[data-theme-toggle], #themeToggle, .theme-toggle"
  );

  const savedTheme = localStorage.getItem("ai-news-theme");

  if (savedTheme === "light") {
    document.body.classList.add("light-mode");
  }

  if (themeButton) {
    themeButton.addEventListener("click", () => {
      document.body.classList.toggle("light-mode");

      const currentTheme = document.body.classList.contains("light-mode")
        ? "light"
        : "dark";

      localStorage.setItem("ai-news-theme", currentTheme);
    });
  }

  /* ---------------------------------------------------------
     3. MOBILE NAVIGATION
     --------------------------------------------------------- */

  const menuButton = document.querySelector(
    "[data-menu-toggle], #menuToggle, .menu-toggle"
  );

  const navigation = document.querySelector(
    "[data-navigation], #mainNavigation, .main-navigation, nav"
  );

  if (menuButton && navigation) {
    menuButton.addEventListener("click", () => {
      navigation.classList.toggle("is-open");
      menuButton.classList.toggle("is-active");

      const expanded = navigation.classList.contains("is-open");

      menuButton.setAttribute("aria-expanded", expanded);
    });
  }

  /* ---------------------------------------------------------
     4. SEARCH INTERFACE
     --------------------------------------------------------- */

  const searchButton = document.querySelector(
    "[data-search-toggle], #searchToggle, .search-toggle"
  );

  const searchPanel = document.querySelector(
    "[data-search-panel], #searchPanel, .search-panel"
  );

  const searchInput = document.querySelector(
    "[data-search-input], #searchInput, .search-input"
  );

  if (searchButton && searchPanel) {
    searchButton.addEventListener("click", () => {
      searchPanel.classList.toggle("is-open");

      if (
        searchPanel.classList.contains("is-open") &&
        searchInput
      ) {
        setTimeout(() => {
          searchInput.focus();
        }, 100);
      }
    });
  }

  if (searchInput) {
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        const query = searchInput.value.trim();

        if (!query) {
          return;
        }

        window.location.href =
          "search.html?q=" + encodeURIComponent(query);
      }
    });
  }

  /* ---------------------------------------------------------
     5. NAVIGATION LINKS
     --------------------------------------------------------- */

  const navigationLinks = document.querySelectorAll(
    "[data-category], .category-link"
  );

  navigationLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      const category = link.dataset.category;

      if (!category) {
        return;
      }

      event.preventDefault();

      window.location.href =
        "category.html?category=" +
        encodeURIComponent(category);
    });
  });

  /* ---------------------------------------------------------
     6. STORY LINKS
     --------------------------------------------------------- */

  const storyLinks = document.querySelectorAll(
    "[data-story], .story-link"
  );

  storyLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      const slug =
        link.dataset.story ||
        link.dataset.slug;

      if (!slug) {
        return;
      }

      event.preventDefault();

      window.location.href =
        "article.html?slug=" +
        encodeURIComponent(slug);
    });
  });

  /* ---------------------------------------------------------
     7. NEWSLETTER
     --------------------------------------------------------- */

  const newsletterForms = document.querySelectorAll(
    "[data-newsletter-form], .newsletter-form"
  );

  newsletterForms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const emailInput = form.querySelector(
        'input[type="email"]'
      );

      if (!emailInput) {
        return;
      }

      const email = emailInput.value.trim();

      if (!email) {
        alert("Please enter your email address.");
        return;
      }

      if (!emailInput.checkValidity()) {
        alert("Please enter a valid email address.");
        return;
      }

      alert(
        "You're on the list. AI News Factory will keep you updated."
      );

      emailInput.value = "";
    });
  });

  /* ---------------------------------------------------------
     8. BACK TO TOP
     --------------------------------------------------------- */

  const backToTop = document.querySelector(
    "[data-back-to-top], #backToTop, .back-to-top"
  );

  if (backToTop) {
    window.addEventListener("scroll", () => {
      if (window.scrollY > 500) {
        backToTop.classList.add("is-visible");
      } else {
        backToTop.classList.remove("is-visible");
      }
    });

    backToTop.addEventListener("click", () => {
      window.scrollTo({
        top: 0,
        behavior: "smooth"
      });
    });
  }

  /* ---------------------------------------------------------
     9. SMOOTH INTERNAL LINKS
     --------------------------------------------------------- */

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      const targetId = link.getAttribute("href");

      if (!targetId || targetId === "#") {
        return;
      }

      const target = document.querySelector(targetId);

      if (!target) {
        return;
      }

      event.preventDefault();

      target.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    });
  });

  /* ---------------------------------------------------------
     10. ESCAPE KEY
     --------------------------------------------------------- */

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }

    if (searchPanel) {
      searchPanel.classList.remove("is-open");
    }

    if (navigation) {
      navigation.classList.remove("is-open");
    }
  });

  /* ---------------------------------------------------------
     11. ACTIVE NAVIGATION
     --------------------------------------------------------- */

  const currentPage =
    window.location.pathname.split("/").pop() ||
    "index.html";

  document.querySelectorAll("nav a").forEach((link) => {
    const href = link.getAttribute("href");

    if (!href) {
      return;
    }

    const linkPage = href.split("?")[0].split("#")[0];

    if (
      linkPage === currentPage ||
      (currentPage === "" && linkPage === "index.html")
    ) {
      link.classList.add("active");
    }
  });

  /* ---------------------------------------------------------
     12. STORY CARD HOVER / ACCESSIBILITY
     --------------------------------------------------------- */

  document.querySelectorAll(
    ".story-card, .hero-story, .latest-story, .trending-item"
  ).forEach((card) => {
    card.addEventListener("keydown", (event) => {
      if (
        event.key !== "Enter" &&
        event.key !== " "
      ) {
        return;
      }

      const link = card.querySelector("a");

      if (!link) {
        return;
      }

      event.preventDefault();
      link.click();
    });
  });

  /* ---------------------------------------------------------
     13. LIVE NEWSROOM INDICATOR
     --------------------------------------------------------- */

  const liveIndicators = document.querySelectorAll(
    "[data-live-indicator], .live-indicator"
  );

  liveIndicators.forEach((indicator) => {
    indicator.setAttribute("aria-label", "Newsroom live");
  });

  /* ---------------------------------------------------------
     14. YEAR
     --------------------------------------------------------- */

  const yearElements = document.querySelectorAll(
    "[data-current-year]"
  );

  yearElements.forEach((element) => {
    element.textContent = new Date().getFullYear();
  });

  /* ---------------------------------------------------------
     15. FACTORY STATUS
     --------------------------------------------------------- */

  const statusElements = document.querySelectorAll(
    "[data-factory-status]"
  );

  statusElements.forEach((element) => {
    element.textContent = "NEWSROOM ONLINE";
    element.classList.add("online");
  });

  console.log(
    "%cAI NEWS FACTORY",
    "font-size:18px;font-weight:bold;"
  );

  console.log(
    "Newsroom interface initialized successfully."
  );
});
