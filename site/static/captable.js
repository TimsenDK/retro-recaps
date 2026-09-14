(function () {
    var table = document.querySelector("tr.cap") && document.querySelector("tr.cap").closest("table");
    if (!table) {
        return;
    }
    table.classList.add("folds");

    // Ticks are kept per page, in this browser only. Storage can be missing or
    // refuse writes (private windows, blocked site data); the boxes then still
    // work for the visit.
    var key = "ticks:" + location.pathname;
    var saved = {};
    try {
        saved = JSON.parse(localStorage.getItem(key) || "{}") || {};
    } catch (error) {
        saved = {};
    }

    function store() {
        try {
            localStorage.setItem(key, JSON.stringify(saved));
        } catch (error) {
            // Nothing to do: the tick stands for this visit.
        }
    }

    Array.prototype.forEach.call(table.querySelectorAll("tr.cap"), function (row, index) {
        var box = row.querySelector(".tick input");
        var fold = row.querySelector(".fold");
        // Index and label together, so a list that gains or loses a line does
        // not carry a tick onto a different capacitor.
        var id = index + ":" + (box.getAttribute("aria-label") || "");

        box.checked = saved[id] === true;
        box.addEventListener("change", function () {
            if (box.checked) {
                saved[id] = true;
            } else {
                delete saved[id];
            }
            store();
        });
        box.addEventListener("click", function (event) {
            event.stopPropagation();
        });

        // The button is the keyboard route; its click bubbles to the row, so
        // the row's handler is the one place a line opens.
        fold.hidden = false;
        row.addEventListener("click", function (event) {
            if (event.target.closest(".tick")) {
                return;
            }
            var open = row.classList.toggle("open");
            fold.setAttribute("aria-expanded", open ? "true" : "false");
        });
    });
})();
