const navToggle = document.getElementById("navToggle");
const siteNav = document.getElementById("siteNav");

if (navToggle && siteNav) {
    navToggle.addEventListener("click", function () {
        const isOpen = siteNav.classList.toggle("is-open");
        navToggle.classList.toggle("is-open", isOpen);
        navToggle.setAttribute("aria-label", isOpen ? "إغلاق القائمة" : "فتح القائمة");
    });

    siteNav.querySelectorAll("a").forEach(function (link) {
        link.addEventListener("click", function () {
            siteNav.classList.remove("is-open");
            navToggle.classList.remove("is-open");
            navToggle.setAttribute("aria-label", "فتح القائمة");
        });
    });
}

const revealItems = document.querySelectorAll(".idea-step, .feature-row");

if (revealItems.length && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.18 }
    );

    revealItems.forEach(function (item) {
        observer.observe(item);
    });
} else {
    revealItems.forEach(function (item) {
        item.classList.add("is-visible");
    });
}
