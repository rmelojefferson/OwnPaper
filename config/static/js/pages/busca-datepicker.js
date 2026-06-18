(function () {
    var wrappers = Array.prototype.slice.call(document.querySelectorAll("[data-busca-datepicker]"));
    if (!wrappers.length) {
        return;
    }

    var monthNames = [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro"
    ];

    var today = new Date();
    var openWrapper = null;

    function startOfDay(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate());
    }

    function parseDate(value) {
        var text = (value || "").trim();
        if (!text) {
            return null;
        }

        var iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (iso) {
            var isoDate = new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
            if (
                isoDate.getFullYear() === Number(iso[1]) &&
                isoDate.getMonth() === Number(iso[2]) - 1 &&
                isoDate.getDate() === Number(iso[3])
            ) {
                return startOfDay(isoDate);
            }
            return null;
        }

        var br = text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        if (br) {
            var brDate = new Date(Number(br[3]), Number(br[2]) - 1, Number(br[1]));
            if (
                brDate.getFullYear() === Number(br[3]) &&
                brDate.getMonth() === Number(br[2]) - 1 &&
                brDate.getDate() === Number(br[1])
            ) {
                return startOfDay(brDate);
            }
        }

        return null;
    }

    function formatDate(date) {
        var day = String(date.getDate()).padStart(2, "0");
        var month = String(date.getMonth() + 1).padStart(2, "0");
        var year = String(date.getFullYear());
        return day + "/" + month + "/" + year;
    }

    function sameDay(a, b) {
        return !!a && !!b &&
            a.getFullYear() === b.getFullYear() &&
            a.getMonth() === b.getMonth() &&
            a.getDate() === b.getDate();
    }

    function clearInvalid(input) {
        input.classList.remove("is-invalid");
    }

    function markInvalid(input) {
        input.classList.add("is-invalid");
    }

    function syncPair(states) {
        var from = states.from ? parseDate(states.from.input.value) : null;
        var to = states.to ? parseDate(states.to.input.value) : null;

        if (from && to && from.getTime() > to.getTime()) {
            states.to.input.value = formatDate(from);
            clearInvalid(states.to.input);
        }
    }

    function closePopover(state) {
        state.wrapper.classList.remove("is-open");
        state.wrapper.classList.remove("is-open-up");
        state.popover.hidden = true;
        if (openWrapper === state.wrapper) {
            openWrapper = null;
        }
    }

    function closeAll(exceptWrapper) {
        wrappers.forEach(function (wrapper) {
            if (wrapper !== exceptWrapper) {
                var state = wrapper.__datepickerState;
                if (state) {
                    closePopover(state);
                }
            }
        });
    }

    function monthLabel(date) {
        return monthNames[date.getMonth()] + " " + date.getFullYear();
    }

    function addMonths(date, amount) {
        return new Date(date.getFullYear(), date.getMonth() + amount, 1);
    }

    function dateBounds(states, role) {
        return {
            min: role === "to" && states.from ? parseDate(states.from.input.value) : null,
            max: role === "from" && states.to ? parseDate(states.to.input.value) : null
        };
    }

    function renderCalendar(state, states) {
        clearInvalid(state.input);
        state.monthLabel.textContent = monthLabel(state.viewDate);
        while (state.grid.firstChild) {
            state.grid.removeChild(state.grid.firstChild);
        }

        var selected = parseDate(state.input.value);
        var bounds = dateBounds(states, state.role);
        var monthStart = new Date(state.viewDate.getFullYear(), state.viewDate.getMonth(), 1);
        var firstWeekday = (monthStart.getDay() + 6) % 7;
        var gridStart = new Date(monthStart);
        gridStart.setDate(monthStart.getDate() - firstWeekday);

        for (var i = 0; i < 42; i += 1) {
            var current = new Date(gridStart);
            current.setDate(gridStart.getDate() + i);
            var button = document.createElement("button");
            button.type = "button";
            button.className = "busca-datepicker-day";
            button.textContent = String(current.getDate());
            button.setAttribute("data-datepicker-value", formatDate(current));

            if (current.getMonth() !== state.viewDate.getMonth()) {
                button.classList.add("is-outside");
            }
            if (sameDay(current, selected)) {
                button.classList.add("is-selected");
            }
            if (sameDay(current, today)) {
                button.classList.add("is-today");
            }

            if (
                (bounds.min && current.getTime() < bounds.min.getTime()) ||
                (bounds.max && current.getTime() > bounds.max.getTime())
            ) {
                button.disabled = true;
            }

            button.addEventListener("click", function (event) {
                var date = parseDate(event.currentTarget.getAttribute("data-datepicker-value"));
                if (!date) {
                    return;
                }
                state.input.value = formatDate(date);
                clearInvalid(state.input);
                syncPair(states);
                renderCalendar(state, states);
                closePopover(state);
            });

            state.grid.appendChild(button);
        }
    }

    function viewportHeight() {
        if (window.visualViewport && window.visualViewport.height) {
            return window.visualViewport.height;
        }
        return window.innerHeight;
    }

    function viewportOffsetTop() {
        if (window.visualViewport && typeof window.visualViewport.offsetTop === "number") {
            return window.visualViewport.offsetTop;
        }
        return 0;
    }

    function updatePopoverPlacement(state) {
        state.wrapper.classList.remove("is-open-up");

        var wrapperRect = state.wrapper.getBoundingClientRect();
        var popoverHeight = state.popover.offsetHeight || 0;
        var viewportTop = viewportOffsetTop();
        var viewportBottom = viewportTop + viewportHeight();
        var safeGap = 16;
        var spaceBelow = viewportBottom - wrapperRect.bottom;
        var spaceAbove = wrapperRect.top - viewportTop;
        var openUp = spaceBelow < popoverHeight + safeGap && spaceAbove > spaceBelow;
        var availableSpace = openUp ? spaceAbove : spaceBelow;
        var maxHeight = Math.max(180, Math.floor(availableSpace - safeGap));

        if (openUp) {
            state.wrapper.classList.add("is-open-up");
        }

        state.popover.style.maxHeight = maxHeight + "px";
        state.popover.style.overflowY = popoverHeight > maxHeight ? "auto" : "visible";
    }

    function normalizeInput(state, states) {
        var parsed = parseDate(state.input.value);
        if (!state.input.value.trim()) {
            clearInvalid(state.input);
            return;
        }
        if (!parsed) {
            markInvalid(state.input);
            return;
        }
        state.input.value = formatDate(parsed);
        clearInvalid(state.input);
        syncPair(states);
    }

    function openPopover(state, states) {
        closeAll(state.wrapper);
        var current = parseDate(state.input.value) || today;
        state.viewDate = new Date(current.getFullYear(), current.getMonth(), 1);
        renderCalendar(state, states);
        state.wrapper.classList.add("is-open");
        state.popover.hidden = false;
        updatePopoverPlacement(state);
        openWrapper = state.wrapper;
    }

    var states = {};

    wrappers.forEach(function (wrapper) {
        var input = wrapper.querySelector("[data-datepicker-input]");
        var toggle = wrapper.querySelector("[data-datepicker-toggle]");
        var popover = wrapper.querySelector("[data-datepicker-popover]");
        var monthNode = wrapper.querySelector("[data-datepicker-month]");
        var grid = wrapper.querySelector("[data-datepicker-grid]");
        var role = wrapper.getAttribute("data-date-role");

        if (!input || !toggle || !popover || !monthNode || !grid || !role) {
            return;
        }

        var state = {
            wrapper: wrapper,
            role: role,
            input: input,
            toggle: toggle,
            popover: popover,
            monthLabel: monthNode,
            grid: grid,
            viewDate: new Date(today.getFullYear(), today.getMonth(), 1)
        };

        wrapper.__datepickerState = state;
        states[role] = state;
    });

    Object.keys(states).forEach(function (role) {
        var state = states[role];
        var prev = state.wrapper.querySelector("[data-datepicker-prev]");
        var next = state.wrapper.querySelector("[data-datepicker-next]");
        var todayButton = state.wrapper.querySelector("[data-datepicker-today]");
        var clearButton = state.wrapper.querySelector("[data-datepicker-clear]");

        state.toggle.addEventListener("mousedown", function (event) {
            event.preventDefault();
        });

        state.toggle.addEventListener("click", function () {
            state.suppressFocusOpenUntil = Date.now() + 250;
            if (state.wrapper.classList.contains("is-open")) {
                closePopover(state);
                return;
            }
            openPopover(state, states);
        });

        state.input.addEventListener("focus", function () {
            if (state.suppressFocusOpenUntil && Date.now() < state.suppressFocusOpenUntil) {
                return;
            }
            openPopover(state, states);
        });

        state.input.addEventListener("blur", function () {
            window.setTimeout(function () {
                normalizeInput(state, states);
            }, 100);
        });

        state.input.addEventListener("input", function () {
            clearInvalid(state.input);
        });

        state.input.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closePopover(state);
            }
        });

        prev.addEventListener("click", function () {
            state.viewDate = addMonths(state.viewDate, -1);
            renderCalendar(state, states);
        });

        next.addEventListener("click", function () {
            state.viewDate = addMonths(state.viewDate, 1);
            renderCalendar(state, states);
        });

        todayButton.addEventListener("click", function () {
            state.input.value = formatDate(today);
            clearInvalid(state.input);
            syncPair(states);
            state.viewDate = new Date(today.getFullYear(), today.getMonth(), 1);
            renderCalendar(state, states);
            closePopover(state);
        });

        clearButton.addEventListener("click", function () {
            state.input.value = "";
            clearInvalid(state.input);
            if (states.from && states.to) {
                clearInvalid(states.from.input);
                clearInvalid(states.to.input);
            }
            closePopover(state);
        });

        normalizeInput(state, states);
    });

    document.addEventListener("click", function (event) {
        if (!openWrapper) {
            return;
        }
        if (openWrapper.contains(event.target)) {
            return;
        }
        var state = openWrapper.__datepickerState;
        if (state) {
            closePopover(state);
        }
    });

    window.addEventListener("resize", function () {
        if (!openWrapper || !openWrapper.__datepickerState) {
            return;
        }
        updatePopoverPlacement(openWrapper.__datepickerState);
    });

    window.addEventListener("scroll", function () {
        if (!openWrapper || !openWrapper.__datepickerState) {
            return;
        }
        updatePopoverPlacement(openWrapper.__datepickerState);
    }, { passive: true });
}());
