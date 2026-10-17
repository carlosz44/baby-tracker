(function () {
  const dataEl = document.getElementById("kick-stats-data");
  if (!dataEl || !window.Chart) return;

  const data = JSON.parse(dataEl.textContent);
  const root = document.querySelector(".viz-root");
  const DAY = 24 * 60 * 60 * 1000;
  // Chart x values are Lima wall-clock times encoded as UTC.
  const dayFormat = new Intl.DateTimeFormat("es", { timeZone: "UTC", day: "numeric", month: "short" });
  let charts = [];

  function palette() {
    const css = getComputedStyle(root);
    const v = (name) => css.getPropertyValue(name).trim();
    return {
      series: v("--viz-series"),
      seriesHover: v("--viz-series-hover"),
      muted: v("--viz-muted-mark"),
      warning: v("--viz-warning"),
      surface: v("--viz-surface"),
      text: v("--viz-text"),
      strong: v("--viz-text-strong"),
      grid: v("--viz-grid"),
      axis: v("--viz-axis"),
    };
  }

  function minutes(value) {
    return `${value.toLocaleString("es", { maximumFractionDigits: 1 })} min`;
  }

  function tooltip(c, callbacks) {
    return {
      backgroundColor: c.strong,
      titleColor: c.surface,
      bodyColor: c.surface,
      titleFont: { size: 14, weight: "600" },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 8,
      displayColors: false,
      callbacks,
    };
  }

  function trendChart(c) {
    const normal = data.points.filter((p) => !p.flagged);
    const flagged = data.points.filter((p) => p.flagged);
    const stepDays = Math.max(1, Math.ceil((data.x_max - data.x_min) / DAY / 6));
    const datasets = [
      {
        label: "Sesión",
        data: normal,
        backgroundColor: c.muted,
        borderColor: c.surface,
        borderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 6,
        pointHitRadius: 10,
        order: 1,
      },
      {
        label: "Mediana 7 días",
        data: data.line,
        showLine: true,
        borderColor: c.series,
        backgroundColor: c.series,
        borderWidth: 2,
        borderCapStyle: "round",
        borderJoinStyle: "round",
        pointRadius: 0,
        pointHitRadius: 0,
        pointStyle: "line",
        order: 2,
      },
    ];
    if (flagged.length) {
      datasets.push({
        label: "Más lenta de lo habitual",
        data: flagged,
        pointStyle: "triangle",
        backgroundColor: c.warning,
        borderColor: c.surface,
        borderWidth: 2,
        pointRadius: 7,
        pointHoverRadius: 8,
        pointHitRadius: 10,
        order: 0,
      });
    }

    return new Chart(document.getElementById("trend-chart"), {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "nearest", intersect: true },
        scales: {
          x: {
            type: "linear",
            min: data.x_min,
            max: data.x_max,
            ticks: { stepSize: stepDays * DAY, color: c.text, maxRotation: 0, callback: (v) => dayFormat.format(new Date(v)) },
            grid: { display: false },
            border: { color: c.axis },
          },
          y: {
            beginAtZero: true,
            ticks: { color: c.text, precision: 0 },
            title: { display: true, text: "min", color: c.text },
            grid: { color: c.grid },
            border: { display: false },
          },
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: { usePointStyle: true, boxWidth: 8, boxHeight: 8, color: c.text, sort: (a, b) => a.datasetIndex - b.datasetIndex },
          },
          tooltip: tooltip(c, {
            title: (items) => `${minutes(items[0].raw.y)} hasta 10`,
            label: (item) => {
              const p = item.raw;
              const lines = [p.label];
              if (p.week !== null) lines.push(`Semana ${p.week}`);
              if (p.baseline !== null) lines.push(`Habitual: ${minutes(p.baseline)}`);
              if (p.flagged) lines.push("▲ Más lenta de lo habitual");
              if (p.notes) lines.push(p.notes);
              return lines;
            },
          }),
        },
      },
    });
  }

  function hoursChart(c) {
    const buckets = data.buckets;
    const capLabels = {
      id: "capLabels",
      afterDatasetsDraw(chart) {
        const { ctx, scales } = chart;
        ctx.save();
        ctx.font = `12px ${Chart.defaults.font.family}`;
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        buckets.forEach((b, i) => {
          const x = scales.x.getPixelForValue(i);
          const y = scales.y.getPixelForValue(b.median ?? 0) - 4;
          ctx.fillStyle = b.median === null ? c.text : c.strong;
          ctx.fillText(b.median === null ? "sin datos" : minutes(b.median), x, y);
        });
        ctx.restore();
      },
    };

    return new Chart(document.getElementById("hours-chart"), {
      type: "bar",
      data: {
        labels: buckets.map((b) => b.label),
        datasets: [
          {
            label: "Mediana hasta 10",
            data: buckets.map((b) => b.median),
            backgroundColor: c.series,
            hoverBackgroundColor: c.seriesHover,
            borderRadius: 4,
            maxBarThickness: 24,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        layout: { padding: { top: 20 } },
        scales: {
          x: { ticks: { color: c.text, maxRotation: 0, autoSkip: false }, grid: { display: false }, border: { color: c.axis } },
          y: {
            beginAtZero: true,
            ticks: { color: c.text, precision: 0 },
            title: { display: true, text: "min", color: c.text },
            grid: { color: c.grid },
            border: { display: false },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: tooltip(c, {
            title: (items) => minutes(buckets[items[0].dataIndex].median),
            label: (item) => {
              const b = buckets[item.dataIndex];
              return [`${b.label} (${b.hours})`, `${b.count} ${b.count === 1 ? "sesión" : "sesiones"}`];
            },
          }),
        },
      },
      plugins: [capLabels],
    });
  }

  function render() {
    charts.forEach((chart) => chart.destroy());
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    const c = palette();
    charts = [trendChart(c), hoursChart(c)];
  }

  render();
  // The theme toggle flips the "dark" class on <html>; repaint with that mode's colors.
  new MutationObserver(render).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
})();
