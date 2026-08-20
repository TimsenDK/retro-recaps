// Client-side filter over the generated index. Without this file the page
// still lists every machine and every family; this only narrows what is
// already there.
(function () {
    "use strict";

    var entries = window.RETRO_SEARCH;
    var box = document.getElementById("search-box");
    var keys = document.getElementById("search-keys");
    var input = document.getElementById("search");
    var results = document.getElementById("search-results");
    var everything = document.getElementById("everything");
    if (!entries || !box || !input || !results || !everything) {
        return;
    }

    // The sheet hides everything the script is responsible for until this
    // marker says the script ran. It decides *whether* they show; the sheet
    // decides how they lay out, so the key row keeps its flex row.
    document.documentElement.classList.add("js");

    // The index writes values as "3300 µf 25 v". A reader types "3300µF",
    // or "3300uf" because µ is on no keyboard, or pastes the Greek mu from
    // somewhere else. All three mean the same position, so the filter folds
    // them together rather than answering "nothing matches" to a search that
    // is right in every way that matters.
    function fold(text) {
        return text
            .toLowerCase()
            .replace(/μ/g, "µ")   // Greek small mu -> micro sign
            .replace(/u(?=f)/g, "µ");  // 'uf' -> 'µf', but 'u' alone stands
    }

    function compact(text) {
        return fold(text).replace(/\s+/g, "");
    }

    var haystacks = entries.map(function (entry) {
        return { loose: fold(entry.text), tight: compact(entry.text) };
    });

    function card(entry) {
        var li = document.createElement("li");
        // The family accent, so a result looks like the card it stands for.
        // An entry with no family keeps the site accent, which is what the
        // stylesheet falls back to.
        li.className = entry.family ? "card fam-" + entry.family : "card";
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
        var terms = fold(input.value).split(/\s+/).filter(Boolean);
        if (!terms.length) {
            results.hidden = true;
            results.textContent = "";
            everything.hidden = false;
            return;
        }
        var matches = entries.filter(function (entry, index) {
            var hay = haystacks[index];
            return terms.every(function (term) {
                return hay.loose.indexOf(term) !== -1
                    || hay.tight.indexOf(compact(term)) !== -1;
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

    // Insert at the caret rather than appending: someone correcting the
    // middle of "3300F 25 v" should get the µ where they are looking.
    function insert(text) {
        var start = input.selectionStart;
        var end = input.selectionEnd;
        if (typeof start !== "number" || typeof end !== "number") {
            input.value += text;
        } else {
            var value = input.value;
            input.value = value.slice(0, start) + text + value.slice(end);
            var caret = start + text.length;
            input.setSelectionRange(caret, caret);
        }
        input.focus();
        render();
    }

    if (keys) {
        keys.addEventListener("click", function (event) {
            var button = event.target.closest("button[data-insert]");
            if (button) {
                insert(button.getAttribute("data-insert"));
            }
        });
    }

    input.addEventListener("input", render);
    render();
})();
