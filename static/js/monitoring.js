function showTab(tab) {
    document.getElementById("harvest").classList.add("hidden");
    document.getElementById("plant").classList.add("hidden");
    document.getElementById(tab).classList.remove("hidden");
}

const barOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } }
};

new Chart(document.getElementById("harvestMonthlyChart"), {
    type: "line",
    data: {
        labels: harvest_months,
        datasets: [{
            label: "Total Harvest Weight (kg)",
            backgroundColor: "#4ade80",
            data: harvest_weights_by_month
        }]
    },
    options: barOptions
});

new Chart(document.getElementById("harvestWeightChart"), {
    type: "pie",
    data: {
        labels: harvest_commodities,
        datasets: [{
            label: "Weight per Commodity (kg)",
            backgroundColor: "#60a5fa",
            data: harvest_weights_by_commodity
        }]
    },
    options: barOptions
});

new Chart(document.getElementById("harvestLocationChart"), {
    type: "bar",
    data: {
        labels: harvest_locations,
        datasets: [{
            label: "Weight by Location (kg)",
            backgroundColor: "#facc15",
            data: harvest_weights_by_location
        }]
    },
    options: barOptions
});

new Chart(document.getElementById("plantCommodityChart"), {
    type: "bar",
    data: {
        labels: plant_commodities,
        datasets: [{
            label: "Planted Units per Commodity",
            backgroundColor: "#34d399",
            data: plant_units_by_commodity
        }]
    },
    options: barOptions
});

new Chart(document.getElementById("plantLandAreaChart"), {
    type: "bar",
    data: {
        labels: plant_commodities,
        datasets: [{
            label: "Avg. Land Area per Commodity (sqm)",
            backgroundColor: "#818cf8",
            data: plant_land_area_by_commodity
        }]
    },
    options: barOptions
});

new Chart(document.getElementById("plantLocationChart"), {
    type: "doughnut",
    data: {
        labels: plant_locations,
        datasets: [{
            label: "Plant Count per Location",
            backgroundColor: "#fb7185",
            data: plant_count_by_location
        }]
    },
    options: barOptions
});