const avgWeightCtx = document.getElementById('avgWeightChart').getContext('2d');
console.log("");

new Chart(avgWeightCtx, {
    type: 'bar',
    data: {
        labels: commodityLabels,
        datasets: [{
            label: 'Avg. Weight per Unit (kg)',
            data: commodityAvgWeight,
            backgroundColor: 'rgba(255, 159, 64, 0.6)',
            borderColor: 'rgba(255, 159, 64, 1)',
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        scales: { y: { beginAtZero: true } }
    }
});