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
    return document.querySelector(`.nav-btn[onclick*="showTab('${tabId}'"]`);
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
function showTab(tabId, btn, updateHash = true) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    if (btn) btn.classList.add('active');
    document.getElementById('page-title').textContent = document.querySelector('#' + tabId + ' .section-title')?.textContent || tabId;

    if (tabId === 'trends') {
        requestAnimationFrame(() => initTrendsCharts());
    } else {
        requestAnimationFrame(() => resizeVisibleCharts());
    }

    if (updateHash) {
        const url = new URL(window.location.href);
        url.hash = tabId;
        history.replaceState({}, '', url);
    }
}

function toggleTheme() {
    const body = document.body;
    const current = body.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    body.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
}

function toggleView(tab, view, btn) {
    applyViewState(tab, view);
    localStorage.setItem(`dashboard:view:${tab}`, view);
}

function searchCards(query) {
    const q = query.toLowerCase().trim();
    document.querySelectorAll('.search-target').forEach(card => {
        const text = (card.dataset.search || card.textContent || '').toLowerCase();
        const shouldShow = !q || text.includes(q);
        
        if (shouldShow) {
            card.style.display = 'block';
            card.style.opacity = '0';
            setTimeout(() => card.style.opacity = '1', 10);
        } else {
            card.style.display = 'none';
        }
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

function openDigest() {
    fetch('/api/digest').then(r => r.json()).then(d => {
        if (d.error) { alert(d.error); return; }
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

// Init theme
const savedTheme = localStorage.getItem('theme') || 'light';
document.body.setAttribute('data-theme', savedTheme);

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
    
    // 's' - Go to Saved tab
    if (e.key === 's' || e.key === 'S') {
        e.preventDefault();
        const savedBtn = document.querySelector('.nav-btn[onclick*="saved"]');
        if (savedBtn) savedBtn.click();
    }
    
    // 'f' - Go to Feed tab
    if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        const feedBtn = document.querySelector('.nav-btn[onclick*="feed"]');
        if (feedBtn) feedBtn.click();
    }
    
    // 'Escape' - Close modals
    if (e.key === 'Escape') {
        const digestModal = document.getElementById('digest-modal');
        if (digestModal && digestModal.classList.contains('open')) {
            closeDigest();
        }
    }
});
