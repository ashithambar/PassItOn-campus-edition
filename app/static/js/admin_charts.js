// PassItOn – Admin Analytics with Chart.js

document.addEventListener('DOMContentLoaded', function () {
    const categoryCanvas = document.getElementById('chart-categories');
    const ordersCanvas = document.getElementById('chart-orders');
    const conditionsCanvas = document.getElementById('chart-conditions');

    if (!categoryCanvas && !ordersCanvas) return;

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
                                '#0f766e', '#0284c7', '#4f46e5', '#7c3aed',
                                '#db2777', '#ea580c', '#ca8a04', '#16a34a',
                                '#0d9488', '#64748b', '#e11d48'
                            ],
                            borderWidth: 2,
                            borderColor: '#ffffff'
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
                            backgroundColor: '#0f766e',
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
                            backgroundColor: ['#10b981', '#38bdf8', '#818cf8', '#fbbf24'],
                            borderWidth: 2,
                            borderColor: '#ffffff'
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
