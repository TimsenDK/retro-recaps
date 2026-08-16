// Client-side filter over the generated index. Without this file the page
// still lists every machine and every family; this only narrows what is
// already there.
(function () {
    "use strict";

    var entries = window.RETRO_SEARCH;
    var box = document.getElementById("search-box");
    var input = document.getElementById("search");
    var results = document.getElementById("search-results");
    var everything = document.getElementById("everything");
    if (!entries || !box || !input || !results || !everything) {
        return;
    }

    box.style.display = "block";

    function card(entry) {
        var li = document.createElement("li");
        li.className = "card";
        var link = document.createElement("a");
        link.href = entry.url;
        link.textContent = entry.title;
        var meta = document.createElement("span");
        meta.className = "meta";
        meta.textContent = entry.subtitle;
        li.appendChild(link);
        li.appendChild(meta);
        return li;
    }

    function render() {
        var terms = input.value.toLowerCase().split(/\s+/).filter(Boolean);
        if (!terms.length) {
            results.hidden = true;
            results.textContent = "";
            everything.hidden = false;
            return;
        }
        var matches = entries.filter(function (entry) {
            return terms.every(function (term) {
                return entry.text.indexOf(term) !== -1;
            });
        });
        results.textContent = "";
        if (!matches.length) {
            var li = document.createElement("li");
            li.className = "card";
            li.textContent = "Nothing matches. Try a designator, a value, or "
                + "a machine name.";
            results.appendChild(li);
        } else {
            matches.slice(0, 40).forEach(function (entry) {
                results.appendChild(card(entry));
            });
        }
        results.hidden = false;
        everything.hidden = true;
    }

    input.addEventListener("input", render);
    render();
})();
