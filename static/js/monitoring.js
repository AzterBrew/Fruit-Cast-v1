const harvestMonthlyChart = new Chart(document.getElementById('harvestMonthlyChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: harvest_months,
            datasets: [{
                label: 'Total Harvested Weight (Kg)',
                data: harvest_weights_by_month,
                borderColor: 'rgb(75, 192, 192)',
                fill: false,
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function (tooltipItem) {
                            return tooltipItem.raw + " Kg";
                        }
                    }
                }
            }
        }
    });

    // HARVEST BY COMMODITY CHART
    const harvestWeightChart = new Chart(document.getElementById('harvestWeightChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: harvest_commodities,
            datasets: [{
                label: 'Harvested Weight by Commodity (Kg)',
                data: harvest_weights_by_commodity,
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgb(75, 192, 192)',
                borderWidth: 1
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function (tooltipItem) {
                            return tooltipItem.raw + " Kg";
                        }
                    }
                }
            }
        }
    });

    // HARVEST BY MUNICIPALITY CHART
    const harvestLocationChart = new Chart(document.getElementById('harvestLocationChart').getContext('2d'), {
        type: 'pie',
        data: {
            labels: harvest_municipality,
            datasets: [{
                label: 'Harvested Weight by Municipality (Kg)',
                data: harvest_weights_by_location,
                backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
                borderColor: '#fff',
                borderWidth: 1
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function (tooltipItem) {
                            return tooltipItem.raw + " Kg";
                        }
                    }
                }
            }
        }
    });

    // PLANT CHARTS

    // PLANT COMMODITIES CHART
    const plantCommodityChart = new Chart(document.getElementById('plantCommodityChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: plant_commodities,
            datasets: [{
                label: 'Number of Plantings',
                data: plant_units_by_commodity,
                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                borderColor: 'rgba(153, 102, 255, 1)',
                borderWidth: 1
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function (tooltipItem) {
                            return tooltipItem.raw + " units";
                        }
                    }
                }
            }
        }
    });

    // ESTIMATED WEIGHT CHART
    const plantEstimatedWeightChart = new Chart(document.getElementById('plantEstimatedWeightChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: plant_estimated_labels,
            datasets: [{
                label: 'Estimated Weight by Commodity (Kg)',
                data: plant_estimated_values,
                backgroundColor: 'rgba(255, 159, 64, 0.2)',
                borderColor: 'rgba(255, 159, 64, 1)',
                borderWidth: 1
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function (tooltipItem) {
                            return tooltipItem.raw + " Kg";
                        }
                    }
                }
            }
        }
    });

    // AVERAGE LAND AREA CHART
    const plantLandAreaChart = new Chart(document.getElementById('plantLandAreaChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: plant_land_area_labels,
            datasets: [{
                label: 'Average Land Area by Commodity (sq. meters)',
                data: plant_land_area_values,
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 1
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function (tooltipItem) {
                            return tooltipItem.raw + " sq. meters";
                        }
                    }
                }
            }
        }
    });

    // PLANT BY LOCATION CHART
    const plantLocationChart = new Chart(document.getElementById('plantLocationChart').getContext('2d'), {
        type: 'pie',
        data: {
            labels: plant_location_labels,
            datasets: [{
                label: 'Plantings by Location',
                data: plant_location_values,
                backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
                borderColor: '#fff',
                borderWidth: 1
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function (tooltipItem) {
                            return tooltipItem.raw + " plantings";
                        }
                    }
                }
            }
        }
    });


// function showTab(tab) {
//     document.getElementById("harvest").classList.add("hidden");
//     document.getElementById("plant").classList.add("hidden");
//     document.getElementById(tab).classList.remove("hidden");
// }


// const labels = harvest_labels;
// const data = harvest_weights;
// const ctx = document.getElementById('harvestMonthlyChart').getContext('2d'); //FOR FILTERS

// const barOptions = {
//     responsive: true,
//     plugins: { legend: { display: false } },
//     scales: { y: { beginAtZero: true } }
// };

// const harvestMonthlyChart = new Chart(document.getElementById("harvestMonthlyChart"), {
//     type: "line",
//     data: {
//         labels: harvest_months,
//         datasets: [{
//             label: "Total Harvest Weight (kg)",
//             backgroundColor: "#4ade80",
//             data: harvest_weights_by_month
//         }]
//     },
//     options: barOptions
// });

// new Chart(document.getElementById("harvestWeightChart"), {
//     type: "pie",
//     data: {
//         labels: harvest_commodities,
//         datasets: [{
//             label: "Weight per Commodity (kg)",
//             backgroundColor: "#60a5fa",
//             data: harvest_weights_by_commodity
//         }]
//     },
//     options: barOptions
// });

// new Chart(document.getElementById("harvestLocationChart"), {
//     type: "bar",
//     data: {
//         labels: harvest_municipality,
//         datasets: [{
//             label: "Weight by Location (kg)",
//             backgroundColor: "#facc15",
//             data: harvest_weights_by_location
//         }]
//     },
//     options: barOptions
// });

// new Chart(document.getElementById("plantCommodityChart"), {
//     type: "bar",
//     data: {
//         labels: plant_commodities,
//         datasets: [{
//             label: "Planted Units per Commodity",
//             backgroundColor: "#34d399",
//             data: plant_units_by_commodity
//         }]
//     },
//     options: barOptions
// });

// new Chart(document.getElementById("plantLandAreaChart"), {
//     type: "bar",
//     data: {
//         labels: plant_commodities,
//         datasets: [{
//             label: "Avg. Land Area per Commodity (sqm)",
//             backgroundColor: "#818cf8",
//             data: plant_land_area_by_commodity
//         }]
//     },
//     options: barOptions
// });

// new Chart(document.getElementById("plantLocationChart"), {
//     type: "doughnut",
//     data: {
//         labels: plant_municipality,
//         datasets: [{
//             label: "Plant Count per Location",
//             backgroundColor: "#fb7185",
//             data: plant_count_by_location
//         }]
//     },
//     options: barOptions
// });

// function harvestMonthlyChart_filter(input_id) {
//     const filterdatavalues = input_id;

//     // const filterData = harvestMonthlyChart.data.datasets[0].data.filter(value => value === 2023);
//     // const filterLabel = [];// harvestMonthlyChart.data.labels[]

//     // let i = 0;
//     // for (i; i < filterData.length; i++){
//     //     const resultindex = harvestMonthlyChart.data.datasets[0].data.indexOf(filterData[i]);
//     //     const filterlabelvalues = harvestMonthlyChart.data.labels[resultindex];
//     //     filterLabel.push(filterlabelvalues);        
//     // }

//     // harvestMonthlyChart.data.datasets[0].data = filterData;
//     // harvestMonthlyChart.data.labels = filterLabel;

//     // harvestMonthlyChart.update();

//     // console.log(filterdatavalues);
//     window.location.href = "?year=" + filterdatavalues;
// }

// // function applyMonthFilter() {
// //   const month = document.getElementById("monthDropdown").value;
// //   const year = document.getElementById("yearDropdown").value;
// //   let url = "?";

// //   if (year) {
// //     url += "year=" + year + "&";
// //   }
// //   if (month) {
// //     url += "month=" + month;
// //   }

// //   window.location.href = url;
// // }

//     const forecastChart = new Chart(ctx, {
//         type: 'line',
//         data: {
//             labels: labels,
//             datasets: [{
//                 label: 'Forecasted Unit Count',
//                 data: forecastedData,
//                 borderColor: 'rgba(75, 192, 192, 1)',
//                 backgroundColor: 'rgba(75, 192, 192, 0.2)',
//                 borderWidth: 2,
//                 tension: 0.3,
//                 fill: true,
//             }]
//         }, 
//         options: {
//             responsive: true,
//             scales: {
//                 y: {
//                     beginAtZero: true,
//                     title: {
//                         display: true,
//                         text: 'Unit Count'
//                     }
//                 },
//                 x: {
//                     title: {
//                         display: true,
//                         text: 'Forecasted Month'
//                     }
//                 }
//             }
//         }
//     });