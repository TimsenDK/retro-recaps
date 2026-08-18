(function () {
    // Nothing on a page with no map: the query fails and the script exits
    // before touching anything, so a board with no layout is unaffected.
    var map = document.querySelector(".boardmap svg");
    if (!map) {
        return;
    }

    var rows = Array.prototype.slice.call(
        document.querySelectorAll("tr[data-designator]")
    );

    function designatorsOf(row) {
        return (row.getAttribute("data-designator") || "").split(/\s+/).filter(Boolean);
    }

    function positionsFor(row) {
        return designatorsOf(row)
            .map(function (designator) {
                return map.querySelector("#pos-" + CSS.escape(designator));
            })
            .filter(Boolean);
    }

    function rowFor(position) {
        var designator = position.id.replace(/^pos-/, "");
        for (var index = 0; index < rows.length; index += 1) {
            if (designatorsOf(rows[index]).indexOf(designator) !== -1) {
                return rows[index];
            }
        }
        return null;
    }

    function light(elements, on) {
        elements.forEach(function (element) {
            element.classList.toggle("lit", on);
        });
    }

    rows.forEach(function (row) {
        var linked = positionsFor(row);
        if (!linked.length) {
            return;
        }
        row.addEventListener("pointerenter", function () {
            light(linked, true);
        });
        row.addEventListener("pointerleave", function () {
            light(linked, false);
        });
        row.addEventListener("click", function () {
            var pinned = row.classList.toggle("pinned");
            linked.forEach(function (position) {
                position.classList.toggle("pinned", pinned);
            });
        });
    });

    Array.prototype.forEach.call(map.querySelectorAll(".pos"), function (position) {
        var row = rowFor(position);
        if (!row) {
            return;
        }
        position.addEventListener("pointerenter", function () {
            light([row], true);
        });
        position.addEventListener("pointerleave", function () {
            light([row], false);
        });
    });
})();
