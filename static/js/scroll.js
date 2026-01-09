document.addEventListener("DOMContentLoaded", function () {
    const links = document.querySelectorAll(".scroll-link");

    links.forEach(link => {
        link.addEventListener("click", function (e) {
            const href = this.getAttribute("href");

            // If link contains hash (#about or #contact)
            if (href.includes("#")) {
                const targetId = href.split("#")[1];

                // If we are already on home page
                if (window.location.pathname === "/" || window.location.pathname === "") {
                    e.preventDefault();
                    scrollToSection(targetId);
                }
            }
        });
    });

    // Scroll on page load if URL has hash
    if (window.location.hash) {
        const targetId = window.location.hash.substring(1);
        setTimeout(() => {
            scrollToSection(targetId);
        }, 100);
    }

    function scrollToSection(id) {
        const section = document.getElementById(id);
        if (section) {
            section.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }
    }
});
