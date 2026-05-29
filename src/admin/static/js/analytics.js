/**
 * Analytics charts initialization (TASK-060).
 *
 * Reads data from <script type="application/json" id="analytics-data">
 * and initializes Chart.js charts.
 */

(function () {
    "use strict";

    /**
     * Reads analytics data from JSON script block.
     * @returns {Object|null} Parsed data or null if missing.
     */
    function getAnalyticsData() {
        const scriptEl = document.getElementById("analytics-data");
        if (!scriptEl) {
            return null;
        }
        try {
            return JSON.parse(scriptEl.textContent);
        } catch (e) {
            console.error("Failed to parse analytics data:", e);
            return null;
        }
    }

    /**
     * Initializes daily prediction counts chart (line).
     * @param {Array} dailyData - Array of {date, count} objects.
     */
    function initDailyChart(dailyData) {
        const canvas = document.getElementById("dailyChart");
        if (!canvas || !dailyData || dailyData.length === 0) {
            return;
        }

        const labels = dailyData.map((d) => d.date);
        const counts = dailyData.map((d) => d.count);

        new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Прогнозы",
                        data: counts,
                        borderColor: "#8b5cf6",
                        backgroundColor: "rgba(139, 92, 246, 0.1)",
                        fill: true,
                        tension: 0.3,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: "index",
                        intersect: false,
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 },
                    },
                },
            },
        });
    }

    /**
     * Initializes category accuracy chart (bar).
     * @param {Array} categoryData - Array of category accuracy objects.
     */
    function initCategoryChart(categoryData) {
        const canvas = document.getElementById("categoryChart");
        if (!canvas || !categoryData || categoryData.length === 0) {
            return;
        }

        const labels = categoryData.map((c) => c.category_name);
        const accuracy = categoryData.map((c) => c.accuracy || 0);

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Точность %",
                        data: accuracy,
                        backgroundColor: [
                            "#8b5cf6",
                            "#3b82f6",
                            "#10b981",
                            "#f59e0b",
                            "#ef4444",
                            "#ec4899",
                            "#6366f1",
                            "#14b8a6",
                        ],
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                    },
                },
            },
        });
    }

    /**
     * Initializes all analytics charts on DOMContentLoaded.
     */
    function initCharts() {
        // Check if Chart is loaded from CDN
        if (typeof Chart === "undefined") {
            console.error("Chart.js is not loaded.");
            return;
        }

        const data = getAnalyticsData();
        if (!data) {
            console.error("Analytics data not found.");
            return;
        }

        initDailyChart(data.daily_counts || []);
        initCategoryChart(data.category_accuracy || []);
    }

    // Initialize on DOMContentLoaded
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCharts);
    } else {
        // DOM already loaded
        initCharts();
    }
})();
