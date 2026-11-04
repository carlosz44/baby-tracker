// Live countdown on the dashboard. The server renders the initial values, so
// this only keeps them moving and swaps to the final message at zero.
(function () {
  var root = document.querySelector("[data-birth-countdown]");
  if (!root) {
    return;
  }

  var target = Date.parse(root.dataset.birthCountdown);
  if (isNaN(target)) {
    return;
  }

  var clock = root.querySelector("[data-countdown-clock]");
  var done = root.querySelector("[data-countdown-done]");
  var timer;

  function show(unit, value, pad) {
    root.querySelector('[data-countdown-value="' + unit + '"]').textContent =
      pad && value < 10 ? "0" + value : String(value);
    var label = root.querySelector('[data-countdown-label="' + unit + '"]');
    label.textContent = value === 1 ? label.dataset.one : label.dataset.many;
  }

  function tick() {
    var left = Math.floor((target - Date.now()) / 1000);
    if (left <= 0) {
      clock.hidden = true;
      done.hidden = false;
      clearInterval(timer);
      return;
    }
    show("days", Math.floor(left / 86400), false);
    show("hours", Math.floor((left % 86400) / 3600), true);
    show("minutes", Math.floor((left % 3600) / 60), true);
    show("seconds", left % 60, true);
  }

  timer = setInterval(tick, 1000);
  tick();
})();
