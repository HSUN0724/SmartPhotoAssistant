document.addEventListener("DOMContentLoaded", () => {
    const navbar = document.getElementById("navbarNav");
    const navigation = document.querySelector(".navbar");
    const progress = document.getElementById("scroll-progress");
    const focusFrame = document.querySelector(".vf-focus");
    const heroVisual = document.querySelector(".hero-visual");

    requestAnimationFrame(() => {
        requestAnimationFrame(() => document.body.classList.add("page-ready"));
    });

    function updatePageChrome() {
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const scrollable = document.documentElement.scrollHeight - window.innerHeight;
        navigation?.classList.toggle("is-scrolled", scrollTop > 18);
        if (progress) {
            const percentage = scrollable > 0 ? Math.min(100, (scrollTop / scrollable) * 100) : 0;
            progress.style.transform = `scaleX(${percentage / 100})`;
        }
    }

    updatePageChrome();
    window.addEventListener("scroll", updatePageChrome, { passive: true });

    navbar?.querySelectorAll(".nav-link").forEach((link) => {
        link.addEventListener("click", () => {
            if (window.innerWidth < 992 && navbar.classList.contains("show")) {
                bootstrap.Collapse.getOrCreateInstance(navbar).hide();
            }
        });
    });

    const revealElements = document.querySelectorAll(".reveal");
    revealElements.forEach((element, index) => {
        element.style.setProperty("--reveal-delay", `${Math.min(index % 4, 3) * 80}ms`);
    });

    if (!("IntersectionObserver" in window)) {
        revealElements.forEach((element) => {
            element.classList.add("is-visible");
        });
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: "0px 0px -4%" });

    revealElements.forEach((element) => observer.observe(element));

    document.querySelectorAll(".btn, .photo-source-card, .feature-card").forEach((element) => {
        element.addEventListener("pointerdown", () => element.classList.add("is-pressed"));
        ["pointerup", "pointerleave", "pointercancel"].forEach((eventName) => {
            element.addEventListener(eventName, () => element.classList.remove("is-pressed"));
        });
    });

    if (focusFrame && window.matchMedia("(pointer: fine)").matches) {
        document.addEventListener("pointerdown", (event) => {
            if (event.button !== 0 || event.target.closest("a, button, input, select, label")) return;

            const overlayBounds = focusFrame.parentElement.getBoundingClientRect();
            focusFrame.style.left = `${event.clientX - overlayBounds.left}px`;
            focusFrame.style.top = `${event.clientY - overlayBounds.top}px`;
            focusFrame.classList.remove("is-locking");
            void focusFrame.offsetWidth;
            focusFrame.classList.add("is-locking");
        });
    }

    if (heroVisual && window.matchMedia("(pointer: fine)").matches) {
        heroVisual.addEventListener("pointermove", (event) => {
            const bounds = heroVisual.getBoundingClientRect();
            const x = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
            const y = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
            heroVisual.style.setProperty("--pointer-x", x.toFixed(3));
            heroVisual.style.setProperty("--pointer-y", y.toFixed(3));
            heroVisual.style.setProperty("--lens-light-x", `${38 + x * 2}%`);
            heroVisual.style.setProperty("--lens-light-y", `${30 + y * 2}%`);
            heroVisual.style.setProperty("--reflection-x", `${27 + x * 1.5}%`);
            heroVisual.style.setProperty("--reflection-y", `${22 + y}%`);
        });

        heroVisual.addEventListener("pointerleave", () => {
            heroVisual.style.setProperty("--pointer-x", "0");
            heroVisual.style.setProperty("--pointer-y", "0");
            heroVisual.style.removeProperty("--lens-light-x");
            heroVisual.style.removeProperty("--lens-light-y");
            heroVisual.style.removeProperty("--reflection-x");
            heroVisual.style.removeProperty("--reflection-y");
        });
    }
});
