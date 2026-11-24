// PassItOn – Admin Analytics with Chart.js

document.addEventListener('DOMContentLoaded', function () {
    const categoryCanvas = document.getElementById('chart-categories');
    const ordersCanvas = document.getElementById('chart-orders');
    const conditionsCanvas = document.getElementById('chart-conditions');

    if (!categoryCanvas && !ordersCanvas) return;

    Chart.defaults.color = '#450920';

    fetch('/admin/api/stats')
        .then(res => res.json())
        .then(data => {
            // 1. Categories Chart (Doughnut)
            if (categoryCanvas && data.categories) {
                new Chart(categoryCanvas, {
                    type: 'doughnut',
                    data: {
                        labels: data.categories.labels,
                        datasets: [{
                            data: data.categories.counts,
                            backgroundColor: [
                                '#DA627D', '#A53860', '#450920', '#FFA5AB',
                                '#DA627D', '#A53860', '#450920', '#FFA5AB',
                                '#DA627D', '#A53860', '#450920'
                            ],
                            borderWidth: 2,
                            borderColor: '#FFFFFF'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: { boxWidth: 12, font: { size: 11 } }
                            }
                        }
                    }
                });
            }

            // 2. Orders Status Chart (Bar)
            if (ordersCanvas && data.orders) {
                new Chart(ordersCanvas, {
                    type: 'bar',
                    data: {
                        labels: data.orders.labels,
                        datasets: [{
                            label: 'Orders Count',
                            data: data.orders.counts,
                            backgroundColor: '#A53860',
                            borderRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: { stepSize: 1 }
                            }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }

            // 3. Item Conditions Chart (Pie)
            if (conditionsCanvas && data.conditions) {
                new Chart(conditionsCanvas, {
                    type: 'pie',
                    data: {
                        labels: data.conditions.labels,
                        datasets: [{
                            data: data.conditions.counts,
                            backgroundColor: ['#DA627D', '#A53860', '#450920', '#FFA5AB'],
                            borderWidth: 2,
                            borderColor: '#FFFFFF'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { boxWidth: 12, font: { size: 11 } }
                            }
                        }
                    }
                });
            }
        })
        .catch(err => console.error("Error loading admin chart data:", err));
});
