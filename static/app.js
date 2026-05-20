// Global state
let charts = {};
let isLoading = false;
let loadedItems = 20;
const itemsPerLoad = 20;
let trendsChartsInitialized = false;
let chartLibraryWarned = false;
let dashboardState = {};
let livePollTimer = null;
let liveUpdatePending = false;
let liveRefreshInFlight = false;
const LIVE_POLL_VISIBLE_MS = 60000;
const LIVE_POLL_HIDDEN_MS = 180000;
const VIEW_TABS = ['github', 'models', 'research'];

function toggleSidebar() {
    var sidebar = document.querySelector('.sidebar');
    var toggle = document.querySelector('.sidebar-toggle');
    if (sidebar && toggle) {
        sidebar.classList.toggle('open');
        toggle.classList.toggle('open');
    }
}

// Desktop sidebar collapse — chevron button inside sidebar
function collapseSidebar() {
    var sidebar = document.getElementById('main-sidebar');
    if (!sidebar) return;
    var collapsed = sidebar.classList.toggle('collapsed');
    try { localStorage.setItem('dailydex-sidebar-collapsed', collapsed ? '1' : '0'); } catch(e) {}
}

// Restore sidebar collapse state on load
(function() {
    try {
        if (localStorage.getItem('dailydex-sidebar-collapsed') === '1') {
            var sidebar = document.getElementById('main-sidebar');
            if (sidebar) sidebar.classList.add('collapsed');
        }
    } catch(e) {}
})();

// Daily Brief rail tab switcher
function briefTab(btn, panelId) {
    var rail = document.getElementById('brief-rail');
    if (!rail) return;
    rail.querySelectorAll('.brief-tab').forEach(function(t) { t.classList.remove('active'); });
    rail.querySelectorAll('.brief-rail-body').forEach(function(p) { p.hidden = true; });
    btn.classList.add('active');
    var panel = document.getElementById(panelId);
    if (panel) panel.hidden = false;
}

function toggleTheme() {
    var body = document.body;
    var current = body.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    body.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    
    var btn = document.querySelector('.theme-toggle-btn');
    if (btn) {
        btn.textContent = next === 'dark' ? '🌙' : '☀️';
    }
}

async function exportSaved(format, pipelineType = '') {
    try {
        var url = '/api/saved/export?format=' + format;
        if (pipelineType) {
            url += '&pipeline_type=' + encodeURIComponent(pipelineType);
        }
        var res = await fetch(url);
        if (format === 'markdown') {
            var text = await res.text();
            var blob = new Blob([text], {type: 'text/markdown'});
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'saved-intelligence.md';
            a.click();
        } else {
            var data = await res.json();
            var json = JSON.stringify(data.items, null, 2);
            var blob = new Blob([json], {type: 'application/json'});
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'saved-intelligence.json';
            a.click();
        }
    } catch (e) {
        console.error('Export failed:', e);
    }
}

let savedCheckboxes = [];
function toggleAllSaved(checked) {
    document.querySelectorAll('.saved-card input[type="checkbox"]').forEach(cb => {
        cb.checked = checked;
    });
}

function toggleSavedBulkBar() {
    var checked = document.querySelectorAll('.saved-card input[type="checkbox"]:checked').length;
    var bar = document.querySelector('.saved-bulk-actions');
    if (bar) {
        bar.style.display = checked > 0 ? 'flex' : 'none';
    }
}

async function bulkUpdateStatus(status) {
    var checked = document.querySelectorAll('.saved-card input[type="checkbox"]:checked');
    for (var cb of checked) {
        var card = cb.closest('.saved-card');
        var id = card.dataset.id;
        if (id) {
            await fetch('/api/saved/' + id + '/status', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status: status})
            });
        }
    }
    location.reload();
}

async function bulkDelete() {
    var checked = document.querySelectorAll('.saved-card input[type="checkbox"]:checked');
    if (!confirm('Delete ' + checked.length + ' items?')) return;
    for (var cb of checked) {
        var card = cb.closest('.saved-card');
        var id = card.dataset.id;
        if (id) {
            await fetch('/api/saved/' + id, {method: 'DELETE'});
        }
    }
    location.reload();
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', function(e) {
    var sidebar = document.querySelector('.sidebar');
    var toggle = document.querySelector('.sidebar-toggle');
    if (sidebar && sidebar.classList.contains('open')) {
        if (!sidebar.contains(e.target) && (!toggle || !toggle.contains(e.target))) {
            sidebar.classList.remove('open');
            toggle.classList.remove('open');
        }
    }
    
    const btn = e.target.closest('.nav-btn[data-tab]');
    if (btn) {
        const tabId = btn.getAttribute('data-tab');
        showTab(tabId, btn);
        e.preventDefault();
        e.stopPropagation();
        
        var sidebar = document.querySelector('.sidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
            var toggle = document.querySelector('.sidebar-toggle');
            if (toggle) toggle.classList.remove('open');
        }
    }
});

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    readDashboardState();
    restoreViewPreferences();
    restoreTabFromLocation();
    initCharts();
    initProgressiveLoading();
    initEmptyStates();
    restoreSearchFromLocation();
    startLiveUpdates();
});

async function switchVariant(variantKey) {
    try {
        const res = await fetch('/api/variant', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({variant: variantKey})
        });
        const data = await res.json();
        if (data.success) {
            location.reload();
        }
    } catch (e) {
        console.error('Failed to switch variant:', e);
    }
}

function readDashboardState() {
    const stateNode = document.getElementById('dashboard-state');
    if (!stateNode) {
        dashboardState = {};
        return dashboardState;
    }

    try {
        dashboardState = JSON.parse(stateNode.textContent || '{}');
    } catch (_error) {
        dashboardState = {};
    }

    if (dashboardState.snapshot_id) {
        setLiveSnapshotId(dashboardState.snapshot_id);
    }
    const lastUpdatedNode = document.querySelector('.last-updated');
    if (lastUpdatedNode && dashboardState.last_updated_display) {
        lastUpdatedNode.textContent = dashboardState.last_updated_display;
    }
    updateLiveStatus('live', 'Live');
    return dashboardState;
}

function setLiveSnapshotId(snapshotId) {
    if (!snapshotId) return;
    dashboardState.snapshot_id = snapshotId;
}

// Chart.js initialization
function initCharts() {
    if (typeof Chart === 'undefined') {
        if (!chartLibraryWarned) {
            console.warn('Chart.js not available, skipping chart initialization');
            chartLibraryWarned = true;
        }
        return;
    }

    Chart.defaults.font.family = "'Fira Sans', sans-serif";
    Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim();
    Chart.defaults.borderColor = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();

    initSparklines();
    if (isSectionVisible('trends')) {
        initTrendsCharts();
    }
}

function isSectionVisible(sectionId) {
    const section = document.getElementById(sectionId);
    return Boolean(section && section.classList.contains('active'));
}

function initTrendsCharts(force = false) {
    if (typeof Chart === 'undefined') {
        return;
    }

    if (trendsChartsInitialized && !force) {
        resizeVisibleCharts();
        return;
    }

    initRadarChart();
    initHeatmapChart();
    initTreemapChart();
    initBubbleChart();
    trendsChartsInitialized = true;
    resizeVisibleCharts();
}

function resizeVisibleCharts() {
    Object.values(charts).forEach(chart => {
        if (chart && chart.canvas && chart.canvas.offsetParent !== null) {
            chart.resize();
        }
    });
}

function setCanvasAccessibility(canvas, label) {
    if (!canvas) return;
    canvas.setAttribute('tabindex', '0');
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', label);
}

function getChartState() {
    return dashboardState.charts || {};
}

function fallbackSparklineSeries(metric) {
    const fallback = {
        trust: { labels: ['GitHub', 'Models', 'Videos', 'News', 'Papers'], values: [100, 100, 85, 90, 95] },
        new: { labels: ['GitHub', 'Models', 'Videos', 'News', 'Papers'], values: [8, 6, 4, 5, 3] },
        signal: { labels: ['GitHub', 'Models', 'Videos', 'News', 'Papers'], values: [4, 3, 2, 2, 1] },
        saved: { labels: ['To Read', 'To Test', 'Testing', 'Useful', 'Discarded'], values: [2, 1, 0, 1, 0] },
    };
    return fallback[metric] || fallback.new;
}

function getSparklineSeries(metric) {
    const series = getChartState().sparklines?.[metric];
    if (series && Array.isArray(series.values) && series.values.length) {
        return series;
    }
    return fallbackSparklineSeries(metric);
}

function statusToChartColor(status, colors) {
    const normalized = (status || '').toLowerCase();
    if (normalized.includes('fail')) return colors.danger;
    if (normalized.includes('stale') || normalized.includes('cache')) return colors.warning;
    return colors.primary;
}

// Get theme colors
function getThemeColors() {
    const isDark = document.body.getAttribute('data-theme') === 'dark';
    return {
        primary: isDark ? '#3B82F6' : '#1E40AF',
        primaryLight: isDark ? '#60A5FA' : '#3B82F6',
        cta: '#F59E0B',
        success: '#10B981',
        warning: '#F59E0B',
        danger: '#EF4444',
        info: '#3B82F6',
        bg: isDark ? '#0F172A' : '#F8FAFC',
        surface: isDark ? '#1E293B' : '#FFFFFF',
        text: isDark ? '#F1F5F9' : '#1E3A8A',
        textMuted: isDark ? '#94A3B8' : '#64748B',
        border: isDark ? '#334155' : '#E2E8F0'
    };
}

// Initialize sparkline charts
function initSparklines() {
    const sparklines = document.querySelectorAll('.sparkline');
    const colors = getThemeColors();

    sparklines.forEach(canvas => {
        const metric = canvas.dataset.metric;
        const series = getSparklineSeries(metric);
        const data = series.values;
        
        if (charts[canvas.id]) {
            charts[canvas.id].destroy();
        }

        setCanvasAccessibility(canvas, `${metric} trend for the last 7 days`);

        const gradient = canvas.getContext('2d').createLinearGradient(0, 0, 0, 40);
        gradient.addColorStop(0, colors.primary + '40');
        gradient.addColorStop(1, colors.primary + '00');

        charts[canvas.id] = new Chart(canvas, {
            type: 'line',
            data: {
                labels: series.labels,
                datasets: [{
                    data: data,
                    borderColor: colors.primary,
                    backgroundColor: gradient,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHoverBackgroundColor: colors.primary,
                    pointHoverBorderColor: colors.surface,
                    pointHoverBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        enabled: true,
                        backgroundColor: colors.surface,
                        titleColor: colors.text,
                        bodyColor: colors.textMuted,
                        borderColor: colors.border,
                        borderWidth: 1,
                        padding: 8,
                        displayColors: false,
                        callbacks: {
                            title: (items) => items[0]?.label || metric.charAt(0).toUpperCase() + metric.slice(1),
                            label: (context) => `Value: ${context.raw}`
                        }
                    }
                },
                scales: {
                    x: { display: false },
                    y: { display: false }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                animation: {
                    duration: 300
                }
            }
        });
    });
}

// Initialize radar chart
function initRadarChart() {
    const canvas = document.getElementById('radar-chart');
    if (!canvas) return;

    const colors = getThemeColors();
    const radar = getChartState().radar || {};
    const labels = radar.labels?.length ? radar.labels : ['GitHub', 'Models', 'Videos', 'News', 'Papers'];
    const datasets = radar.datasets?.length ? radar.datasets : [
        { label: 'Average Signal', values: [85, 74, 63, 58, 69] },
        { label: 'Relative Volume', values: [100, 72, 44, 38, 30] },
    ];
    setCanvasAccessibility(canvas, 'Topic radar chart');

    if (charts['radar-chart']) {
        charts['radar-chart'].destroy();
    }

    charts['radar-chart'] = new Chart(canvas, {
        type: 'radar',
        data: {
            labels,
            datasets: datasets.map((dataset, index) => {
                const tone = index === 0 ? colors.primary : colors.cta;
                return {
                    label: dataset.label,
                    data: dataset.values,
                    backgroundColor: tone + '33',
                    borderColor: tone,
                    borderWidth: 2,
                    pointBackgroundColor: tone,
                    pointBorderColor: colors.surface,
                    pointHoverBackgroundColor: colors.surface,
                    pointHoverBorderColor: tone,
                };
            })
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: colors.text,
                        padding: 15,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: colors.surface,
                    titleColor: colors.text,
                    bodyColor: colors.textMuted,
                    borderColor: colors.border,
                    borderWidth: 1
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        color: colors.textMuted,
                        backdropColor: 'transparent'
                    },
                    grid: {
                        color: colors.border
                    },
                    pointLabels: {
                        color: colors.text,
                        font: {
                            size: 11,
                            weight: '500'
                        }
                    }
                }
            },
            animation: {
                duration: 500
            }
        }
    });
}

// Initialize heatmap chart (using bar chart as fallback)
function initHeatmapChart() {
    const canvas = document.getElementById('heatmap-chart');
    if (!canvas) return;

    const colors = getThemeColors();
    const sourceActivity = getChartState().source_activity || {};
    const labels = sourceActivity.labels?.length ? sourceActivity.labels : ['GitHub', 'Models', 'Videos', 'News', 'Papers'];
    const values = sourceActivity.values?.length ? sourceActivity.values : [18, 12, 7, 6, 4];
    const statuses = sourceActivity.statuses || [];
    setCanvasAccessibility(canvas, 'Source activity chart for the last 7 days');

    if (charts['heatmap-chart']) {
        charts['heatmap-chart'].destroy();
    }

    charts['heatmap-chart'] = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Items available',
                data: values,
                backgroundColor: labels.map((_, index) => statusToChartColor(statuses[index], colors) + 'CC'),
                borderColor: labels.map((_, index) => statusToChartColor(statuses[index], colors)),
                borderWidth: 1,
                borderRadius: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    backgroundColor: colors.surface,
                    titleColor: colors.text,
                    bodyColor: colors.textMuted,
                    borderColor: colors.border,
                    borderWidth: 1,
                    callbacks: {
                        label: (context) => `${Math.round(context.raw)} items (${statuses[context.dataIndex] || 'Unknown'})`
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: { color: colors.border },
                    ticks: { color: colors.textMuted }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: colors.textMuted }
                }
            },
            animation: {
                duration: 500
            }
        }
    });
}

// Initialize treemap chart (using bar chart as fallback)
function initTreemapChart() {
    const canvas = document.getElementById('treemap-chart');
    if (!canvas) return;

    const colors = getThemeColors();
    const categories = getChartState().categories || {};
    const labels = categories.labels?.length ? categories.labels : ['Agents', 'Models', 'Research', 'Tools'];
    const values = categories.values?.length ? categories.values : [12, 10, 8, 6];
    const signalScores = categories.scores?.length ? categories.scores : [86, 79, 68, 64];
    setCanvasAccessibility(canvas, 'Category breakdown chart');

    if (charts['treemap-chart']) {
        charts['treemap-chart'].destroy();
    }

    const backgroundColors = signalScores.map(score => {
        if (score >= 80) return colors.danger;
        if (score >= 60) return colors.warning;
        return colors.info;
    });

    charts['treemap-chart'] = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: backgroundColors,
                borderColor: colors.surface,
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: colors.text,
                        padding: 15,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: colors.surface,
                    titleColor: colors.text,
                    bodyColor: colors.textMuted,
                    borderColor: colors.border,
                    borderWidth: 1,
                    callbacks: {
                        label: (context) => {
                            const category = context.label;
                            const count = context.raw;
                            const score = signalScores[context.dataIndex];
                            return [
                                `${category}: ${count} items`,
                                `Signal Score: ${score}`
                            ];
                        }
                    }
                }
            },
            animation: {
                duration: 500
            }
        }
    });
}

// Initialize bubble chart
function initBubbleChart() {
    const canvas = document.getElementById('bubble-chart');
    if (!canvas) return;

    const colors = getThemeColors();
    const savedWorkflow = getChartState().saved_workflow || {};
    setCanvasAccessibility(canvas, 'Saved intelligence bubble chart');

    if (charts['bubble-chart']) {
        charts['bubble-chart'].destroy();
    }

    const sourceColors = {
        github: colors.primary,
        huggingface: colors.cta,
        papers: colors.success,
        blogs: colors.info,
        youtube: colors.warning,
        other: colors.textMuted,
    };

    const datasetsBySource = savedWorkflow.datasets || {};
    const statusAxis = savedWorkflow.status_axis || {
        labels: ['To Read', 'To Test', 'Testing', 'Useful', 'Discarded'],
        values: [20, 40, 60, 80, 100],
    };

    charts['bubble-chart'] = new Chart(canvas, {
        type: 'bubble',
        data: {
            datasets: Object.keys(datasetsBySource).map((sourceType) => ({
                label: sourceType,
                data: datasetsBySource[sourceType],
                backgroundColor: (sourceColors[sourceType] || sourceColors.other) + '80',
                borderColor: sourceColors[sourceType] || sourceColors.other,
                borderWidth: 2
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: colors.text,
                        padding: 15,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: colors.surface,
                    titleColor: colors.text,
                    bodyColor: colors.textMuted,
                    borderColor: colors.border,
                    borderWidth: 1,
                    callbacks: {
                        label: (context) => {
                            const data = context.raw;
                            return [
                                data.title,
                                `Signal: ${data.x}`,
                                `Workflow: ${data.status}`,
                                `Weight: ${data.r}`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Signal Score',
                        color: colors.textMuted
                    },
                    grid: { color: colors.border },
                    ticks: { color: colors.textMuted }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Workflow Stage',
                        color: colors.textMuted
                    },
                    grid: { color: colors.border },
                    ticks: {
                        color: colors.textMuted,
                        callback: (value) => {
                            const axisIndex = (statusAxis.values || []).indexOf(value);
                            return axisIndex >= 0 ? statusAxis.labels[axisIndex] : '';
                        },
                    },
                    min: 0,
                    max: 100,
                }
            },
            animation: {
                duration: 500
            }
        }
    });
}

// Update charts when theme changes
const originalToggleTheme = toggleTheme;
toggleTheme = function() {
    originalToggleTheme();
    setTimeout(() => {
        Object.values(charts).forEach(chart => {
            if (chart) {
                const colors = getThemeColors();
                if (chart.options.plugins?.legend?.labels) {
                    chart.options.plugins.legend.labels.color = colors.text;
                }
                if (chart.options.plugins?.tooltip) {
                    chart.options.plugins.tooltip.backgroundColor = colors.surface;
                    chart.options.plugins.tooltip.titleColor = colors.text;
                    chart.options.plugins.tooltip.bodyColor = colors.textMuted;
                    chart.options.plugins.tooltip.borderColor = colors.border;
                }
                
                if (chart.options.scales) {
                    Object.values(chart.options.scales).forEach(scale => {
                        if (scale.ticks) scale.ticks.color = colors.textMuted;
                        if (scale.grid) scale.grid.color = colors.border;
                        if (scale.title) scale.title.color = colors.textMuted;
                        if (scale.pointLabels) scale.pointLabels.color = colors.text;
                    });
                }
                
                chart.update();
            }
        });
        resizeVisibleCharts();
    }, 100);
};

function destroyCharts() {
    Object.values(charts).forEach(chart => {
        if (chart) {
            try {
                chart.destroy();
            } catch (_error) {
                // Ignore chart teardown errors during DOM swaps.
            }
        }
    });
    charts = {};
    trendsChartsInitialized = false;
}

function getNavButton(tabId) {
    return document.getElementById(`nav-${tabId}`);
}

function captureUIState() {
    const searchInput = document.getElementById('global-search');
    const views = {};
    VIEW_TABS.forEach(tab => {
        const tableView = document.getElementById(`${tab}-table-view`);
        views[tab] = tableView && tableView.style.display !== 'none' ? 'table' : 'card';
    });

    return {
        activeTab: document.querySelector('.section.active')?.id || 'overview',
        searchQuery: searchInput ? searchInput.value : '',
        views,
        scrollY: window.scrollY,
    };
}

function applyViewState(tab, view) {
    const cardView = document.getElementById(`${tab}-card-view`);
    const tableView = document.getElementById(`${tab}-table-view`);
    if (!cardView || !tableView) return;

    cardView.style.display = view === 'card' ? 'grid' : 'none';
    tableView.style.display = view === 'table' ? 'block' : 'none';

    document.querySelectorAll(`[data-view-tab="${tab}"]`).forEach(button => {
        button.classList.toggle('active', button.dataset.viewMode === view);
    });
}

function restoreViewPreferences(preferredViews = null) {
    VIEW_TABS.forEach(tab => {
        const view = preferredViews?.[tab] || localStorage.getItem(`dashboard:view:${tab}`) || 'card';
        applyViewState(tab, view);
    });
}

function restoreTabFromLocation() {
    const requestedTab = (window.location.hash || '#overview').replace('#', '');
    if (!requestedTab || !document.getElementById(requestedTab)) {
        return;
    }

    const button = getNavButton(requestedTab);
    if (button) {
        showTab(requestedTab, button, false);
    }
}

function updateSearchParam(query) {
    const url = new URL(window.location.href);
    if (query) {
        url.searchParams.set('q', query);
    } else {
        url.searchParams.delete('q');
    }
    history.replaceState({}, '', url);
}

function restoreSearchFromLocation() {
    const url = new URL(window.location.href);
    const query = url.searchParams.get('q') || '';
    const searchInput = document.getElementById('global-search');
    if (!searchInput) return;
    searchInput.value = query;
    if (query) {
        originalSearchCards(query);
    }
}

function updateLiveStatus(state, text) {
    const badge = document.getElementById('live-status');
    if (!badge) return;
    badge.dataset.liveState = state;
    const label = badge.querySelector('.live-text');
    if (label && text) {
        label.textContent = text;
    }
}

function startLiveUpdates() {
    scheduleLivePoll();
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && liveUpdatePending && !isUserBusy()) {
            applyPendingLiveRefresh();
            return;
        }
        scheduleLivePoll();
    });
}

function scheduleLivePoll() {
    if (livePollTimer) {
        clearTimeout(livePollTimer);
    }
    const delay = document.hidden ? LIVE_POLL_HIDDEN_MS : (dashboardState.live_interval_seconds || 60) * 1000;
    livePollTimer = setTimeout(pollDashboardMeta, delay);
}

function isUserBusy() {
    const activeElement = document.activeElement;
    const typing = activeElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeElement.tagName);
    const modalOpen = document.getElementById('digest-modal')?.classList.contains('open');
    return liveRefreshInFlight || isLoading || typing || modalOpen;
}

async function pollDashboardMeta() {
    if (isUserBusy()) {
        scheduleLivePoll();
        return;
    }

    updateLiveStatus('checking', 'Checking');
    try {
        const response = await fetch('/api/dashboard-meta', { headers: { 'Accept': 'application/json' } });
        if (!response.ok) {
            updateLiveStatus('stale', 'Offline');
            scheduleLivePoll();
            return;
        }

        const meta = await response.json();
        const currentSnapshotId = dashboardState.snapshot_id;
        if (!currentSnapshotId) {
            setLiveSnapshotId(meta.snapshot_id);
            updateLiveStatus('live', 'Live');
            scheduleLivePoll();
            return;
        }

        if (meta.snapshot_id !== currentSnapshotId) {
            if (isUserBusy()) {
                liveUpdatePending = true;
                updateLiveStatus('pending', 'Update ready');
            } else {
                await refreshDashboardFromServer();
            }
        } else {
            updateLiveStatus('live', 'Live');
            const lastUpdatedNode = document.querySelector('.last-updated');
            if (lastUpdatedNode && meta.last_updated_display) {
                lastUpdatedNode.textContent = meta.last_updated_display;
            }
        }
    } catch (_error) {
        updateLiveStatus('stale', 'Offline');
    }

    scheduleLivePoll();
}

async function applyPendingLiveRefresh() {
    if (!liveUpdatePending && !liveRefreshInFlight) {
        return;
    }
    await refreshDashboardFromServer(true);
}

async function refreshDashboardFromServer(force = false) {
    if (liveRefreshInFlight && !force) {
        return;
    }

    liveRefreshInFlight = true;
    updateLiveStatus('checking', 'Syncing');
    const uiState = captureUIState();

    try {
        const response = await fetch(window.location.pathname + window.location.search, {
            headers: { 'X-Live-Refresh': '1' },
        });
        if (!response.ok) {
            throw new Error('Live refresh failed');
        }

        const html = await response.text();
        const nextDocument = new DOMParser().parseFromString(html, 'text/html');
        const nextMainContent = nextDocument.querySelector('.main-content');
        const currentMainContent = document.querySelector('.main-content');
        const nextSidebarHealth = nextDocument.querySelector('#sidebar-source-health-mini');
        const currentSidebarHealth = document.querySelector('#sidebar-source-health-mini');

        if (!nextMainContent || !currentMainContent) {
            throw new Error('Live refresh markup missing main content');
        }

        destroyCharts();
        currentMainContent.replaceWith(nextMainContent);
        if (nextSidebarHealth && currentSidebarHealth) {
            currentSidebarHealth.replaceWith(nextSidebarHealth);
        }

        readDashboardState();
        restoreViewPreferences(uiState.views);

        const navButton = getNavButton(uiState.activeTab);
        if (navButton) {
            showTab(uiState.activeTab, navButton, false);
        }

        initProgressiveLoading();
        initEmptyStates();
        initCharts();

        const searchInput = document.getElementById('global-search');
        if (searchInput) {
            searchInput.value = uiState.searchQuery;
        }
        if (uiState.searchQuery) {
            originalSearchCards(uiState.searchQuery);
        }

        window.scrollTo({ top: uiState.scrollY, behavior: 'auto' });
        liveUpdatePending = false;
        updateLiveStatus('live', 'Live');
        showToast('Updated', 'New intelligence loaded.', 'success');
    } catch (_error) {
        updateLiveStatus('stale', 'Retry');
    } finally {
        liveRefreshInFlight = false;
        scheduleLivePoll();
    }
}

// Progressive loading
function initProgressiveLoading() {
    const cardGrids = document.querySelectorAll('.card-grid');
    
    cardGrids.forEach(grid => {
        const cards = grid.querySelectorAll('.item-card');
        if (cards.length > itemsPerLoad) {
            for (let i = itemsPerLoad; i < cards.length; i++) {
                cards[i].style.display = 'none';
            }
            
            const loadMoreBtn = document.createElement('button');
            loadMoreBtn.className = 'btn btn-primary load-more-btn';
            loadMoreBtn.textContent = `Load More (${cards.length - itemsPerLoad} remaining)`;
            loadMoreBtn.onclick = () => loadMoreItems(grid, loadMoreBtn, cards);
            
            const container = document.createElement('div');
            container.className = 'load-more-container';
            container.appendChild(loadMoreBtn);
            grid.parentNode.appendChild(container);
        }
    });
}

function loadMoreItems(grid, btn, allCards) {
    btn.classList.add('loading');
    btn.disabled = true;
    
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'loading-indicator';
    loadingIndicator.innerHTML = '<div class="spinner"></div> Loading more items...';
    btn.parentNode.insertBefore(loadingIndicator, btn);
    
    setTimeout(() => {
        const currentlyVisible = Array.from(grid.querySelectorAll('.item-card:not([style*="display: none"])')).length;
        let newlyVisible = 0;
        
        for (let i = currentlyVisible; i < Math.min(currentlyVisible + itemsPerLoad, allCards.length); i++) {
            allCards[i].style.display = 'flex';
            allCards[i].style.opacity = '0';
            setTimeout(() => {
                allCards[i].style.opacity = '1';
            }, newlyVisible * 50);
            newlyVisible++;
        }
        
        loadingIndicator.remove();
        btn.classList.remove('loading');
        
        const remaining = allCards.length - currentlyVisible - newlyVisible;
        if (remaining > 0) {
            btn.textContent = `Load More (${remaining} remaining)`;
            btn.disabled = false;
        } else {
            btn.remove();
        }
    }, 500);
}

// Empty states
function initEmptyStates() {
    const sections = ['feed', 'github', 'models', 'research', 'videos', 'news', 'local', 'saved'];
    
    sections.forEach(sectionId => {
        const section = document.getElementById(sectionId);
        if (!section) return;
        
        const cardGrid = section.querySelector('.card-grid, .kanban-board');
        if (!cardGrid) return;
        
        const items = cardGrid.querySelectorAll('.item-card, .saved-card');
        if (items.length === 0) {
            showEmptyState(cardGrid);
        }
    });
}

function showEmptyState(container) {
    const template = document.getElementById('empty-state-template');
    if (!template) return;
    
    const emptyState = template.content.cloneNode(true);
    const actionBtn = emptyState.querySelector('.empty-state-action');
    
    actionBtn.addEventListener('click', () => {
        const filterBtns = document.querySelectorAll('.filter-btn');
        filterBtns.forEach(btn => btn.classList.remove('active'));
        if (filterBtns[0]) {
            filterBtns[0].classList.add('active');
            filterBtns[0].click();
        }
    });
    
    container.appendChild(emptyState);
}

// Show skeleton screens
function showSkeleton(container, type = 'card') {
    const template = document.getElementById(`skeleton-${type}-template`);
    if (!template) return;
    
    const skeletonCount = type === 'row' ? 5 : 3;
    for (let i = 0; i < skeletonCount; i++) {
        const skeleton = template.content.cloneNode(true);
        container.appendChild(skeleton);
    }
}

// Remove skeleton screens
function removeSkeletons(container) {
    const skeletons = container.querySelectorAll('.skeleton-card, .skeleton-row');
    skeletons.forEach(skeleton => skeleton.remove());
}

// Enhanced toast notification
function showToast(title, message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '<svg class="toast-icon success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        error: '<svg class="toast-icon error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
        warning: '<svg class="toast-icon warning" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
    };
    
    toast.innerHTML = `
        <div class="toast-header">
            ${icons[type] || icons.success}
            <div class="toast-title">${title}</div>
            <button class="toast-close" onclick="dismissToast(this)">×</button>
        </div>
        <div class="toast-message">${message}</div>
    `;
    
    container.appendChild(toast);
    
    // Auto-dismiss after 3 seconds
    const timeout = setTimeout(() => {
        dismissToast(toast.querySelector('.toast-close'));
    }, 3000);
    
    // Pause on hover
    toast.addEventListener('mouseenter', () => clearTimeout(timeout));
    toast.addEventListener('mouseleave', () => {
        setTimeout(() => {
            dismissToast(toast.querySelector('.toast-close'));
        }, 1000);
    });
}

function dismissToast(btn) {
    const toast = btn.closest('.toast');
    toast.classList.add('hiding');
    setTimeout(() => toast.remove(), 300);
}

// Enhanced button loading states
function setButtonLoading(btn, loading, originalText = '') {
    if (loading) {
        btn.dataset.originalText = btn.textContent;
        btn.classList.add('loading');
        btn.disabled = true;
    } else {
        btn.classList.remove('loading');
        btn.disabled = false;
        btn.textContent = btn.dataset.originalText || originalText;
    }
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Debounced search
const debouncedSearch = debounce((query) => {
    originalSearchCards(query);
    updateSearchParam(query);
}, 300);

// Override searchCards to use debounced version
const originalSearchCards = searchCards;
searchCards = function(query) {
    debouncedSearch(query);
};

// Keyboard navigation for charts
document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'CANVAS') {
        const chart = Object.values(charts).find(c => c.canvas === e.target);
        if (!chart) return;
        
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            e.preventDefault();
            const activeElements = chart.getActiveElements();
            const datasetCount = chart.data.datasets.length;
            const dataCount = chart.data.datasets[0].data.length;
            
            if (activeElements.length > 0) {
                const { datasetIndex, index } = activeElements[0];
                let newIndex = index;
                
                if (e.key === 'ArrowRight') {
                    newIndex = (index + 1) % dataCount;
                } else {
                    newIndex = (index - 1 + dataCount) % dataCount;
                }
                
                chart.setActiveElements([{ datasetIndex, index: newIndex }]);
                chart.tooltip.setActiveElements([{ datasetIndex, index: newIndex }]);
                chart.update();
            }
        }
    }
});

window.addEventListener('resize', debounce(() => {
    resizeVisibleCharts();
}, 150));

// Original functions
function showTab(tabId, btn, updateHash) {
    try {
        if (!tabId) return;
        
        var section = document.getElementById(tabId);
        if (!section) {
            console.error('Section not found:', tabId);
            return;
        }
        
        document.querySelectorAll('.section').forEach(function(s) {
            s.classList.remove('active');
            s.style.display = 'none';
        });
        document.querySelectorAll('.nav-btn').forEach(function(b) {
            b.classList.remove('active');
        });
        
        section.classList.add('active');
        section.style.display = 'block';
        if (btn) btn.classList.add('active');
        
        var titleEl = document.getElementById('page-title');
        if (titleEl) {
            var sectionTitle = section.dataset.title || section.querySelector('.section-title')?.textContent || tabId;
            titleEl.textContent = sectionTitle;
        }

        if (tabId === 'trends') {
            if (typeof initTrendsCharts === 'function') {
                requestAnimationFrame(function() { initTrendsCharts(); });
            }
        } else if (tabId === 'forge-studio') {
            if (typeof refreshForgeStudio === 'function') {
                refreshForgeStudio();
            }
        } else {
            if (typeof resizeVisibleCharts === 'function') {
                requestAnimationFrame(function() { resizeVisibleCharts(); });
            }
        }

        if (updateHash !== false) {
            var url = new URL(window.location.href);
            url.hash = tabId;
            history.replaceState({}, '', url);
        }
    } catch (e) {
        console.error('showTab error:', e);
    }
}

function searchCards(query) {
    const q = query.toLowerCase();
    document.querySelectorAll('.search-target').forEach(card => {
        const text = (card.dataset.search || card.textContent || '').toLowerCase();
        card.style.display = text.includes(q) ? 'block' : 'none';
    });
}

function searchTabCards(tabId, query) {
    const q = query.toLowerCase();
    document.querySelectorAll(`#${tabId} .search-target`).forEach(card => {
        const text = (card.dataset.search || card.textContent || '').toLowerCase();
        card.style.display = q === '' || text.includes(q) ? 'block' : 'none';
    });
}

function setCardFilter(mode, btn) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    
    const cards = document.querySelectorAll('#feed .search-target');
    cards.forEach(card => {
        const label = (card.dataset.scoreLabel || '').toLowerCase();
        const shouldShow = mode === 'all' || label.includes(mode);
        
        if (shouldShow) {
            card.style.display = 'block';
            card.style.opacity = '0';
            setTimeout(() => card.style.opacity = '1', 10);
        } else {
            card.style.display = 'none';
        }
    });
}

let currentScoreFilter = 'all';
function setScoreFilter(range, btn) {
    currentScoreFilter = range;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    
    const cards = document.querySelectorAll('#feed .search-target');
    cards.forEach(card => {
        const breakdown = card.dataset.breakdown ? JSON.parse(card.dataset.breakdown) : {};
        const score = breakdown.total || breakdown.signal_score || 0;
        let shouldShow = range === 'all';
        
        if (range === '80+') shouldShow = score >= 80;
        else if (range === '60-79') shouldShow = score >= 60 && score < 80;
        else if (range === '<60') shouldShow = score < 60;
        
        if (shouldShow) {
            card.style.display = 'block';
            card.style.opacity = '0';
            setTimeout(() => card.style.opacity = '1', 10);
        } else {
            card.style.display = 'none';
        }
    });
}

function filterSaved(status, btn) {
    if (btn) {
        btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    document.querySelectorAll('#saved .saved-card').forEach(card => {
        card.style.display = status === 'all' || card.dataset.status === status ? 'flex' : 'none';
    });
}

function refreshNow(button) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'flex';
    isLoading = true;
    
    if (button) { 
        setButtonLoading(button, true);
    }
    
    fetch('/api/refresh', { method: 'POST' }).then(r => r.json()).then(d => {
        if (d.status === 'ok') {
            if (overlay) overlay.style.display = 'none';
            if (button) {
                setButtonLoading(button, false);
            }
            showToast('Success', 'Data refreshed successfully!', 'success');
            setTimeout(() => refreshDashboardFromServer(true), 300);
        } else {
            if (overlay) overlay.style.display = 'none';
            if (button) {
                setButtonLoading(button, false);
            }
            showToast('Error', 'Failed to refresh data. Please try again.', 'error');
        }
    }).catch(() => {
        if (overlay) overlay.style.display = 'none';
        if (button) {
            setButtonLoading(button, false);
        }
        showToast('Error', 'Network error. Please check your connection.', 'error');
    }).finally(() => {
        isLoading = false;
    });
}

function openDigest(mode = 'default') {
    const endpoint = mode === 'creator' ? '/api/creator-digest' : '/api/digest';
    fetch(endpoint).then(r => r.json()).then(d => {
        if (d.error) { alert(d.error); return; }
        const titleNode = document.querySelector('.digest-title');
        if (titleNode) {
            titleNode.textContent = mode === 'creator' ? 'Creator Digest' : "Today's Digest";
        }
        document.getElementById('digest-content').textContent = d.digest || '';
        document.getElementById('digest-modal').classList.add('open');
    });
}

function closeDigest(e) {
    if (!e || e.target.id === 'digest-modal') document.getElementById('digest-modal').classList.remove('open');
}

function copyDigest() {
    navigator.clipboard.writeText(document.getElementById('digest-content').textContent)
        .then(() => {
            showToast('Copied', 'Digest copied to clipboard.', 'success');
        })
        .catch(() => {
            showToast('Error', 'Failed to copy digest.', 'error');
        });
}

function saveItem(item, btn) {
    setButtonLoading(btn, true);
    
    fetch('/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item)
    }).then(r => r.json()).then(d => {
        if (d.success) {
            setButtonLoading(btn, false, 'Saved');
            btn.textContent = 'Saved';
            btn.disabled = true;
            showToast('Saved', d.message || 'Item saved to board.', 'success');
        } else {
            setButtonLoading(btn, false);
            showToast('Error', d.message || 'Failed to save item.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

function saveCreatorItem(item, status, btn) {
    const payload = {
        ...item,
        pipeline_type: 'creator',
        status: status,
        working_title: item.suggested_titles ? (item.suggested_titles.practical || item.title) : item.title,
        hook: item.hook || item.opening_hook,
        format: item.best_format || item.recommended_content_format,
        outline: item.three_key_points || [],
        sources: item.source_evidence || [],
        thumbnail_text: item.thumbnail_text || [],
        notes: item.creator_reason || '',
        priority: item.creator_score >= 80 ? 'high' : item.creator_score >= 60 ? 'medium' : 'low',
        creator_score: item.creator_score,
    };
    saveItem(payload, btn);
}

function buildResearchPack(item, btn) {
    setButtonLoading(btn, true);
    fetch('/api/research-pack', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item),
    }).then(r => r.json()).then(d => {
        if (d.success) {
            setButtonLoading(btn, false, 'Built');
            showToast('Research pack', d.message || 'Research pack generated.', 'success');
        } else {
            setButtonLoading(btn, false);
            showToast('Error', d.error || 'Failed to build research pack.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

function requestEnrichment(item, btn) {
    setButtonLoading(btn, true);
    fetch('/api/enrich', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ...item, force: true }),
    }).then(r => r.json()).then(d => {
        if (d.queued) {
            setButtonLoading(btn, false, 'Queued');
            showToast('Enrichment queued', 'LLM creator pack will appear shortly.', 'success');
            startEnrichmentPolling();
        } else {
            setButtonLoading(btn, false);
            const reason = d.reason || 'unknown';
            showToast('Not queued', `Reason: ${reason}.`, 'info');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

let enrichmentPollTimer = null;

const ENRICHMENT_BADGE_LABELS = {
    ready: 'LLM ✓',
    ready_with_warnings: 'LLM ~',
    queued: 'Queued',
    failed: 'LLM ✗',
    unenriched: 'Draft',
};

function refreshEnrichmentBadge(card) {
    const hash = card.dataset.contentHash;
    if (!hash) return Promise.resolve();
    return fetch(`/api/enrich/${hash}`).then(r => {
        if (!r.ok) return null;
        return r.json();
    }).then(d => {
        if (!d) return;
        const status = d.status || 'unenriched';
        const badge = card.querySelector('.enrichment-badge');
        if (badge) {
            badge.className = `enrichment-badge state-${status}`;
            badge.textContent = ENRICHMENT_BADGE_LABELS[status] || status;
            badge.setAttribute('title', d.error || status);
        }
        card.dataset.enrichment = status;
        if (status === 'ready' || status === 'ready_with_warnings') {
            // Replace inline hook + title text from the fresh pack so the user
            // sees real LLM output without needing a manual reload.
            const pack = d.payload || {};
            const hookEl = card.querySelector('.creator-hook');
            if (hookEl && pack.hook) hookEl.textContent = pack.hook;
            const titleEl = card.querySelector('h3');
            if (titleEl && pack.suggested_titles && pack.suggested_titles.practical) {
                titleEl.textContent = pack.suggested_titles.practical;
            }
        }
    }).catch(() => {});
}

function refreshStaleEnrichmentBadges() {
    const cards = document.querySelectorAll('.creator-opportunity-card[data-content-hash]');
    cards.forEach(card => {
        const state = card.dataset.enrichment || 'unenriched';
        if (state === 'ready' || state === 'ready_with_warnings') return;
        refreshEnrichmentBadge(card);
    });
}

function startEnrichmentPolling() {
    if (enrichmentPollTimer) return;
    enrichmentPollTimer = setInterval(() => {
        fetch('/api/enrich-status').then(r => r.json()).then(d => {
            const el = document.getElementById('enrichment-status-pill');
            if (el) {
                const queued = d.queued || 0;
                const inflight = d.in_flight || 0;
                const ready = (d.cache_counts && d.cache_counts.ready) || 0;
                el.textContent = `LLM: ${ready} ready / ${queued + inflight} pending`;
                el.dataset.state = (queued + inflight) > 0 ? 'working' : 'idle';
            }
            refreshStaleEnrichmentBadges();
            if ((d.queued || 0) === 0 && (d.in_flight || 0) === 0) {
                clearInterval(enrichmentPollTimer);
                enrichmentPollTimer = null;
            }
        }).catch(() => {});
    }, 4000);
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.creator-opportunity-card[data-content-hash][data-enrichment="queued"]')) {
        startEnrichmentPolling();
    }
});

function forgeProductionAssets(itemId, btn) {
    setButtonLoading(btn, true);
    fetch(`/api/forge/${itemId}`, { method: 'POST' }).then(r => r.json()).then(d => {
        if (d.ok) {
            setButtonLoading(btn, false, 'Forging…');
            showToast('Forge started', 'Multi-format assets will appear in a moment.', 'success');
            pollForgeStatus(itemId, btn);
        } else {
            setButtonLoading(btn, false);
            showToast('Forge error', d.error || 'Could not start forge.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

const FORGE_PANE_KEYS = {
    shorts: 'shorts_script',
    podcast: 'podcast_script',
    linkedin: 'linkedin_post',
    blog: 'blog_outline',
    demo: 'demo_guide',
};

function applyForgeAssets(card, assets) {
    if (!card || !assets) return;
    let forgeArea = card.querySelector('.production-forge-area');
    if (!forgeArea) {
        // Build the missing forge area in-place so a freshly-forged item
        // doesn't require a page reload to show the new tabs.
        const editor = card.querySelector('.saved-editor');
        if (!editor) return;
        forgeArea = document.createElement('div');
        forgeArea.className = 'production-forge-area';
        forgeArea.innerHTML = `
            <div class="forge-label">🛠️ Production Forge</div>
            <div class="forge-tabs">
                <button class="forge-tab-btn active" onclick="switchForgeTab(this, 'shorts')">Shorts</button>
                <button class="forge-tab-btn" onclick="switchForgeTab(this, 'podcast')">Podcast</button>
                <button class="forge-tab-btn" onclick="switchForgeTab(this, 'linkedin')">LinkedIn</button>
                <button class="forge-tab-btn" onclick="switchForgeTab(this, 'blog')">Blog</button>
                <button class="forge-tab-btn" onclick="switchForgeTab(this, 'demo')">Demo</button>
            </div>
            <div class="forge-content-area">
                <div class="forge-pane shorts active"></div>
                <div class="forge-pane podcast"></div>
                <div class="forge-pane linkedin"></div>
                <div class="forge-pane blog"></div>
                <div class="forge-pane demo"></div>
            </div>`;
        editor.appendChild(forgeArea);
    }
    Object.entries(FORGE_PANE_KEYS).forEach(([pane, key]) => {
        const target = forgeArea.querySelector(`.forge-pane.${pane}`);
        if (target) target.textContent = assets[key] || '';
    });
}

function pollForgeStatus(itemId, btn) {
    const card = btn ? btn.closest('.creator-saved-card') : null;
    let attempts = 0;
    const max = 30;
    const timer = setInterval(() => {
        attempts += 1;
        fetch(`/api/forge-status/${itemId}`).then(r => r.json()).then(d => {
            const status = d.status || 'none';
            const pill = card ? card.querySelector('.forge-status-pill') : null;
            if (pill) {
                pill.className = `forge-status-pill state-${status}`;
                pill.textContent = status;
            }
            if (status === 'ready') {
                clearInterval(timer);
                setButtonLoading(btn, false, 'Forged');
                applyForgeAssets(card, d.assets || {});
                showToast('Production assets ready', 'Five formats injected below.', 'success');
            } else if (status === 'failed') {
                clearInterval(timer);
                setButtonLoading(btn, false);
                showToast('Forge failed', 'See server logs for details.', 'error');
            } else if (attempts >= max) {
                clearInterval(timer);
                setButtonLoading(btn, false);
                showToast('Forge still running', 'Reload later to see results.', 'info');
            }
        }).catch(() => {});
    }, 4000);
}

function ignoreItem(item, btn) {
    setButtonLoading(btn, true);
    
    fetch('/api/ignore', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item)
    }).then(r => r.json()).then(d => {
        if (d.success) { 
            setButtonLoading(btn, false);
            btn.closest('.item-card').style.display = 'none'; 
            showToast('Ignored', 'Item hidden from feed.', 'success');
        } else {
            setButtonLoading(btn, false);
            showToast('Error', d.message || 'Failed to ignore item.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

function trackItem(item, btn) {
    setButtonLoading(btn, true);
    
    fetch('/api/track', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item)
    }).then(r => r.json()).then(d => {
        if (d.success) { 
            setButtonLoading(btn, false, 'Tracked');
            btn.textContent = 'Tracked'; 
            btn.disabled = true; 
            showToast('Tracking', d.message || 'Topic added to tracking.', 'success');
        } else {
            setButtonLoading(btn, false);
            showToast('Error', d.message || 'Failed to track topic.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

function deleteItem(id, btn) {
    setButtonLoading(btn, true);
    
    fetch('/api/saved/' + id, {method: 'DELETE'}).then(r => r.json()).then(d => {
        if (d.success) { 
            setButtonLoading(btn, false);
            btn.closest('.saved-card').remove(); 
            showToast('Removed', 'Item removed from saved items.', 'success');
        } else {
            setButtonLoading(btn, false);
            showToast('Error', d.message || 'Failed to remove item.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

function updateStatus(id, status) {
    fetch('/api/saved/' + id + '/status', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({status})
    }).then(r => r.json()).then(d => {
        if (d.success) {
            showToast('Updated', `Status changed to ${status}.`, 'success');
        } else {
            showToast('Error', d.message || 'Failed to update status.', 'error');
        }
    }).catch(() => {
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

function updateNotes(id, notes, tags) {
    const btn = event.target;
    setButtonLoading(btn, true);
    
    fetch('/api/saved/' + id + '/notes', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({notes, tags: tags.split(',').map(t => t.trim()).filter(Boolean)})
    }).then(r => r.json()).then(d => {
        if (d.success) {
            setButtonLoading(btn, false, 'Saved');
            showToast('Saved', 'Notes updated successfully.', 'success');
        } else {
            setButtonLoading(btn, false);
            showToast('Error', d.message || 'Failed to update notes.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

function updateCreatorItem(id, card) {
    const btn = event.target;
    setButtonLoading(btn, true);
    const payload = {
        notes: card.querySelector('.creator-notes-input')?.value || '',
        tags: [],
        working_title: card.querySelector('.creator-title-input')?.value || '',
        hook: card.querySelector('.creator-hook-input')?.value || '',
        format: card.querySelector('.creator-format-input')?.value || '',
        outline: (card.querySelector('.creator-outline-input')?.value || '').split('\n').map(line => line.trim()).filter(Boolean),
        thumbnail_text: card.querySelector('.creator-thumb-input')?.value || '',
        priority: card.querySelector('.creator-priority-input')?.value || '',
        published_url: card.querySelector('.creator-published-input')?.value || '',
        pipeline_type: 'creator',
    };

    fetch('/api/saved/' + id + '/notes', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
    }).then(r => r.json()).then(d => {
        if (d.success) {
            setButtonLoading(btn, false, 'Saved');
            showToast('Saved', 'Creator pipeline item updated.', 'success');
        } else {
            setButtonLoading(btn, false);
            showToast('Error', d.message || 'Failed to update creator item.', 'error');
        }
    }).catch(() => {
        setButtonLoading(btn, false);
        showToast('Error', 'Network error. Please try again.', 'error');
    });
}

// Init theme
const savedTheme = localStorage.getItem('theme') || 'light';
document.body.setAttribute('data-theme', savedTheme);
const themeToggleBtn = document.querySelector('.theme-toggle-btn');
if (themeToggleBtn) {
    themeToggleBtn.textContent = savedTheme === 'dark' ? '🌙' : '☀️';
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Don't trigger shortcuts when typing in input fields
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        return;
    }
    
    // '/' - Focus search
    if (e.key === '/') {
        e.preventDefault();
        document.getElementById('global-search').focus();
    }
    
    // '?' - Show shortcuts
    if (e.key === '?') {
        e.preventDefault();
        showShortcuts();
    }
    
    // 's' - Go to Saved tab
    if (e.key === 's' || e.key === 'S') {
        e.preventDefault();
        const savedBtn = document.getElementById('nav-saved');
        if (savedBtn) savedBtn.click();
    }
    
    // 'f' - Go to Feed tab
    if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        const feedBtn = document.getElementById('nav-feed');
        if (feedBtn) feedBtn.click();
    }
    
    // 'Escape' - Close modals
    if (e.key === 'Escape') {
        const digestModal = document.getElementById('digest-modal');
        if (digestModal && digestModal.classList.contains('open')) {
            closeDigest();
        }
        const shortcutsModal = document.getElementById('shortcuts-modal');
        if (shortcutsModal) shortcutsModal.style.display = 'none';
    }
});

function showShortcuts() {
    let modal = document.getElementById('shortcuts-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'shortcuts-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Keyboard Shortcuts</h3>
                    <button class="modal-close" onclick="this.closest('#shortcuts-modal').style.display='none'">&times;</button>
                </div>
                <div class="shortcuts-list">
                    <div class="shortcut"><kbd>/</kbd> Focus search</div>
                    <div class="shortcut"><kbd>s</kbd> Go to Saved</div>
                    <div class="shortcut"><kbd>f</kbd> Go to Feed</div>
                    <div class="shortcut"><kbd>Esc</kbd> Close modal</div>
                    <div class="shortcut"><kbd>?</kbd> Show this help</div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    modal.style.display = 'flex';
}

// --- Friend vote badges ---
async function loadVoteBadges() {
    try {
        const votes = await fetch('/api/votes').then(r => r.json());
        if (!votes || typeof votes !== 'object') return;
        document.querySelectorAll('.item-card[data-url]').forEach(card => {
            const url = card.dataset.url;
            const count = votes[url];
            if (!count) return;
            const badge = card.querySelector('.vote-badge');
            if (!badge) return;
            badge.querySelector('.vote-count').textContent =
                `${count} friend${count > 1 ? 's' : ''} voted`;
            badge.style.display = 'inline-flex';
        });
    } catch (e) {
        // votes API unavailable — silently skip
    }
}

document.addEventListener('DOMContentLoaded', loadVoteBadges);

function switchForgeTab(btn, type) {
    const card = btn.closest('.production-forge-area');
    const tabs = card.querySelectorAll('.forge-tab-btn');
    const panes = card.querySelectorAll('.forge-pane');
    
    tabs.forEach(t => t.classList.remove('active'));
    panes.forEach(p => p.classList.remove('active'));
    
    btn.classList.add('active');
    const activePane = card.querySelector('.forge-pane.' + type);
    if (activePane) activePane.classList.add('active');
}

let activeForgeItem = null;
let activeForgeAssetType = 'shorts';

async function refreshForgeStudio() {
    const list = document.getElementById('forge-item-list');
    list.innerHTML = '<div class="loading">Syncing Pipeline...</div>';
    
    try {
        const res = await fetch('/api/saved?status=script_ready');
        const data = await res.json();
        const items = (data.items || []).filter(i => i.production_status === 'ready' || i.production_assets);
        
        if (items.length === 0) {
            list.innerHTML = '<div class="empty-state">No forged items ready.</div>';
            return;
        }
        
        list.innerHTML = '';
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'forge-item-card';
            if (activeForgeItem && activeForgeItem.id === item.id) card.classList.add('active');
            card.onclick = () => selectForgeItem(item);
            
            card.innerHTML = `
                <div class="forge-item-title">${item.working_title || item.title}</div>
                <div class="forge-item-meta">${item.category} • ${item.source}</div>
            `;
            list.appendChild(card);
        });
    } catch (e) {
        list.innerHTML = '<div class="error">Failed to load pipeline.</div>';
    }
}

function selectForgeItem(item) {
    activeForgeItem = item;
    
    // Update active class in list
    document.querySelectorAll('.forge-item-card').forEach(c => {
        c.classList.remove('active');
        if (c.querySelector('.forge-item-title').innerText === (item.working_title || item.title)) {
            c.classList.add('active');
        }
    });
    
    // Show content
    document.getElementById('forge-main-empty').style.display = 'none';
    document.getElementById('forge-main-content').style.display = 'flex';
    
    // Update headers
    document.getElementById('forge-active-title').innerText = item.working_title || item.title;
    document.getElementById('forge-active-meta').innerText = `${item.category} • ${item.source} • ${item.created_at.split(' ')[0]}`;
    
    // Update context
    document.getElementById('forge-context-leads').innerText = item.notes.split('|')[0] || 'No leads extracted.';
    document.getElementById('forge-context-inversion').innerText = item.notes.includes('INVERSION:') ? item.notes.split('INVERSION:')[1] : 'No risk analysis available.';
    
    // Default to shorts
    switchStudioAsset('shorts');
}

function switchStudioAsset(type) {
    activeForgeAssetType = type;
    
    // Update buttons
    document.querySelectorAll('.forge-asset-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.innerText.toLowerCase().includes(type)) btn.classList.add('active');
    });
    
    // Update label
    const labels = {
        'shorts': '📹 YouTube Shorts Script',
        'podcast': '🎙️ Podcast Dialogue',
        'linkedin': '🔗 LinkedIn Professional Post',
        'blog': '✍️ Technical Blog Outline',
        'demo': '💻 Visual Demo Guide'
    };
    document.getElementById('forge-asset-label').innerText = labels[type];
    
    // Load content
    const assets = typeof activeForgeItem.production_assets === 'string' 
        ? JSON.parse(activeForgeItem.production_assets) 
        : activeForgeItem.production_assets;
        
    const content = assets[type + '_script'] || assets[type + '_post'] || assets[type + '_outline'] || assets[type + '_guide'] || assets[type] || 'Asset not forged for this format.';
    document.getElementById('forge-editor-content').innerText = content;
}

function copyStudioAsset() {
    const text = document.getElementById('forge-editor-content').innerText;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.querySelector('.forge-editor-toolbar .btn');
        const oldText = btn.innerText;
        btn.innerText = 'Copied!';
        btn.classList.add('btn-success');
        setTimeout(() => {
            btn.innerText = oldText;
            btn.classList.remove('btn-success');
        }, 2000);
    });
}

// End of Forge Studio logic

window.selectForgeItem = selectForgeItem;

async function openItemInStudio(itemId) {
    showTab('forge-studio');
    const res = await fetch('/api/saved?status=script_ready');
    const data = await res.json();
    const item = (data.items || []).find(i => i.id === itemId);
    if (item) selectForgeItem(item);
}

// --- Provider logo badges ---
const _SOURCE_ICONS = {
    github: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>',
    youtube: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M23.5 6.19a3.02 3.02 0 0 0-2.12-2.14C19.54 3.55 12 3.55 12 3.55s-7.54 0-9.38.5A3.02 3.02 0 0 0 .5 6.19C0 8.07 0 12 0 12s0 3.93.5 5.81a3.02 3.02 0 0 0 2.12 2.14C4.46 20.45 12 20.45 12 20.45s7.54 0 9.38-.5a3.02 3.02 0 0 0 2.12-2.14C24 15.93 24 12 24 12s0-3.93-.5-5.81zM9.55 15.57V8.43L15.82 12l-6.27 3.57z"/></svg>',
    huggingface: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 36 36" fill="currentColor" aria-hidden="true"><path d="M18 2C9.16 2 2 9.16 2 18s7.16 16 16 16 16-7.16 16-16S26.84 2 18 2zm-4.5 11a2 2 0 1 1 0 4 2 2 0 0 1 0-4zm9 0a2 2 0 1 1 0 4 2 2 0 0 1 0-4zm-9.3 8.5c.4-.26.92-.16 1.18.24.04.06 1.1 1.56 3.62 1.56s3.58-1.5 3.62-1.56a.87.87 0 0 1 1.18-.24.87.87 0 0 1 .24 1.18C22.9 23.28 21.2 25 18 25s-4.9-1.72-5.04-1.82a.87.87 0 0 1-.26-1.18z"/></svg>',
    papers: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
    arxiv: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
    reddit: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .379-.24l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/></svg>',
    hackernews: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M0 24V0h24v24H0zM6.951 5.896l4.112 7.708v5.064h1.583v-4.972l4.148-7.799h-1.749l-2.457 4.875c-.372.745-.688 1.434-.688 1.434s-.297-.708-.651-1.406L8.831 5.896z"/></svg>',
    producthunt: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M13.604 8.4h-3.405V12h3.405c.995 0 1.8-.805 1.8-1.8 0-.995-.805-1.8-1.8-1.8zM12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm1.604 13.8H10.2v4.2H8.4V6h5.204c1.985 0 3.6 1.615 3.6 3.6s-1.615 3.6-3.6 3.6z"/></svg>',
    blogs: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19.01 7.38 20 6.18 20C4.98 20 4 19.01 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/></svg>',
    models: '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
};

function initSourceBadgeIcons() {
    document.querySelectorAll('.badge-source:not([data-iconified])').forEach(function(badge) {
        var sourceClass = Array.from(badge.classList).find(function(c) { return c.startsWith('source-'); });
        if (!sourceClass) return;
        var sourceType = sourceClass.replace('source-', '');
        var icon = _SOURCE_ICONS[sourceType];
        if (!icon) return;
        badge.setAttribute('title', badge.textContent.trim() || sourceType);
        badge.setAttribute('aria-label', sourceType);
        badge.innerHTML = icon;
        badge.setAttribute('data-iconified', '1');
        badge.style.padding = '3px 5px';
        badge.style.lineHeight = '1';
        badge.style.verticalAlign = 'middle';
    });
}

document.addEventListener('DOMContentLoaded', initSourceBadgeIcons);
