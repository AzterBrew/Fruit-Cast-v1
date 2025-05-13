function showTab(tab) {
    document.getElementById("harvest").classList.add("hidden");
    document.getElementById("plant").classList.add("hidden");
    document.getElementById(tab).classList.remove("hidden");
}


const labels = harvest_labels;
const data = harvest_weights;
const ctx = document.getElementById('harvestMonthlyChart').getContext('2d'); //FOR FILTERS

const barOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } }
};

const harvestMonthlyChart = new Chart(document.getElementById("harvestMonthlyChart"), {
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

function harvestMonthlyChart_filter(input_id) {
    const filterdatavalues = input_id;

    // const filterData = harvestMonthlyChart.data.datasets[0].data.filter(value => value === 2023);
    // const filterLabel = [];// harvestMonthlyChart.data.labels[]

    // let i = 0;
    // for (i; i < filterData.length; i++){
    //     const resultindex = harvestMonthlyChart.data.datasets[0].data.indexOf(filterData[i]);
    //     const filterlabelvalues = harvestMonthlyChart.data.labels[resultindex];
    //     filterLabel.push(filterlabelvalues);        
    // }

    // harvestMonthlyChart.data.datasets[0].data = filterData;
    // harvestMonthlyChart.data.labels = filterLabel;

    // harvestMonthlyChart.update();

    // console.log(filterdatavalues);
    window.location.href = "?year=" + filterdatavalues;
}

// function applyMonthFilter() {
//   const month = document.getElementById("monthDropdown").value;
//   const year = document.getElementById("yearDropdown").value;
//   let url = "?";

//   if (year) {
//     url += "year=" + year + "&";
//   }
//   if (month) {
//     url += "month=" + month;
//   }

//   window.location.href = url;
// }

    const forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Forecasted Unit Count',
                data: forecastedData,
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderWidth: 2,
                tension: 0.3,
                fill: true,
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Unit Count'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Forecasted Month'
                    }
                }
            }
        }
    });