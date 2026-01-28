/**
 * CADWR Groundwater Map - Interactive Controls
 */

// Global state
var MapState = {
    homeCenter: { lat: 33.0, lon: -117.0 },
    homeZoom: 9,
    currentZoom: 9,
    plotDiv: null,
    siteTimeSeries: {},
    layerConfig: [],
    layerOriginalData: {}
};

// Initialize map state from config
function initMapState(config) {
    MapState.homeCenter = { lat: config.homeLat, lon: config.homeLon };
    MapState.homeZoom = config.homeZoom;
    MapState.currentZoom = config.homeZoom;
    MapState.siteTimeSeries = config.timeSeries || {};
    MapState.layerConfig = config.layers || [];
}

// Get Plotly div (cached)
function getPlotDiv() {
    if (!MapState.plotDiv) {
        MapState.plotDiv = document.getElementsByClassName('js-plotly-plot')[0];
    }
    return MapState.plotDiv;
}

// Zoom In
function zoomIn(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    try {
        var gd = getPlotDiv();
        if (!gd || !gd.layout || !gd.layout.map) {
            console.warn('Map not ready for zoomIn');
            return false;
        }
        var mapLayout = gd.layout.map;
        var currentLat = mapLayout.center ? mapLayout.center.lat : MapState.homeCenter.lat;
        var currentLon = mapLayout.center ? mapLayout.center.lon : MapState.homeCenter.lon;
        var targetZoom = Math.min((mapLayout.zoom || MapState.currentZoom) + 1, 20);
        Plotly.relayout(gd, {
            'map.zoom': targetZoom,
            'map.center.lat': currentLat,
            'map.center.lon': currentLon
        });
        MapState.currentZoom = targetZoom;
    } catch (err) { console.error('zoomIn error:', err); }
    return false;
}

// Zoom Out
function zoomOut(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    try {
        var gd = getPlotDiv();
        if (!gd || !gd.layout || !gd.layout.map) {
            console.warn('Map not ready for zoomOut');
            return false;
        }
        var mapLayout = gd.layout.map;
        var currentLat = mapLayout.center ? mapLayout.center.lat : MapState.homeCenter.lat;
        var currentLon = mapLayout.center ? mapLayout.center.lon : MapState.homeCenter.lon;
        var targetZoom = Math.max((mapLayout.zoom || MapState.currentZoom) - 1, 1);
        Plotly.relayout(gd, {
            'map.zoom': targetZoom,
            'map.center.lat': currentLat,
            'map.center.lon': currentLon
        });
        MapState.currentZoom = targetZoom;
    } catch (err) { console.error('zoomOut error:', err); }
    return false;
}

// Go Home
function goHome(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    try {
        var gd = getPlotDiv();
        if (!gd) {
            console.warn('Map not ready for goHome');
            return false;
        }
        Plotly.relayout(gd, {
            'map.zoom': MapState.homeZoom,
            'map.center.lat': MapState.homeCenter.lat,
            'map.center.lon': MapState.homeCenter.lon
        });
        MapState.currentZoom = MapState.homeZoom;
    } catch (err) { console.error('goHome error:', err); }
    return false;
}

// Toggle Info Modal
function toggleInfo() {
    var modal = document.getElementById('infoModal');
    modal.style.display = modal.style.display === 'block' ? 'none' : 'block';
}

// Toggle Layer Visibility
function toggleLayer(layerId) {
    var gd = getPlotDiv();
    if (!gd || !gd.data) return;

    var checkbox = document.getElementById('layer-' + layerId);
    var visible = checkbox.checked;

    for (var i = 0; i < gd.data.length; i++) {
        if (gd.data[i].name === layerId) {
            if (!visible) {
                MapState.layerOriginalData[layerId] = {
                    lat: gd.data[i].lat.slice(),
                    lon: gd.data[i].lon.slice()
                };
                Plotly.restyle(gd, { lat: [[]], lon: [[]] }, [i]);
            } else {
                if (MapState.layerOriginalData[layerId]) {
                    Plotly.restyle(gd, {
                        lat: [MapState.layerOriginalData[layerId].lat],
                        lon: [MapState.layerOriginalData[layerId].lon]
                    }, [i]);
                }
            }
            break;
        }
    }
}

// Get Percentile Color
function getPercentileColor(classCode) {
    if (classCode === 1 || classCode === 2) return '#1565C0';  // Blue (good)
    if (classCode === 3 || classCode === 4) return '#43A047';  // Green (normal)
    if (classCode === 5) return '#FF9800';  // Orange (caution)
    if (classCode === 6 || classCode === 7) return '#D32F2F';  // Red (drought)
    return '#757575';  // Gray (not ranked)
}

// Show Marker Popup
function showMarkerPopup(siteNo, data) {
    var header = document.getElementById('popupHeader');
    var body = document.getElementById('popupBody');
    var popup = document.getElementById('markerPopup');
    var overlay = document.getElementById('popupOverlay');

    var source = data.source || 'USGS';
    var sourceColor = source === 'CADWR' ? '#4CAF50' : '#1976D2';

    header.innerHTML = '<span style="background:' + sourceColor + ';padding:2px 8px;border-radius:4px;font-size:11px;margin-right:10px;">' + source + '</span>' + (data.name || 'Site ' + siteNo);

    var html = '';

    // Basic info
    html += '<div class="info-row"><span class="info-label">Site Code</span><span class="info-value">' + siteNo + '</span></div>';
    html += '<div class="info-row"><span class="info-label">Latitude</span><span class="info-value">' + (data.lat ? data.lat.toFixed(6) : 'N/A') + '°</span></div>';
    html += '<div class="info-row"><span class="info-label">Longitude</span><span class="info-value">' + (data.lon ? data.lon.toFixed(6) : 'N/A') + '°</span></div>';

    // Source-specific info
    if (source === 'CADWR') {
        if (data.county) html += '<div class="info-row"><span class="info-label">County</span><span class="info-value">' + data.county + '</span></div>';
        if (data.basin_name) html += '<div class="info-row"><span class="info-label">Basin</span><span class="info-value">' + data.basin_name + '</span></div>';
        if (data.measurement_date) html += '<div class="info-row"><span class="info-label">Last Measured</span><span class="info-value">' + data.measurement_date + '</span></div>';
        if (data.depth_ft !== null && data.depth_ft !== undefined) html += '<div class="info-row"><span class="info-label">Depth to Water</span><span class="info-value">' + data.depth_ft.toFixed(1) + ' ft</span></div>';
        if (data.gwe_ft !== null && data.gwe_ft !== undefined) html += '<div class="info-row"><span class="info-label">GW Elevation</span><span class="info-value">' + data.gwe_ft.toFixed(1) + ' ft</span></div>';
        if (data.percentile_class) html += '<div class="info-row"><span class="info-label">Percentile Class</span><span class="info-value" style="font-weight:600;color:' + getPercentileColor(data.percentile_class_code) + ';">' + data.percentile_class + '</span></div>';
    } else {
        if (data.aquifer_type) html += '<div class="info-row"><span class="info-label">Aquifer Type</span><span class="info-value">' + (data.aquifer_type === 'U' ? 'Unconfined' : 'Confined') + '</span></div>';
    }

    // Percentile Histogram (CADWR only) - rendered with Plotly
    var hasPctData = data.pct_lowest !== null && data.pct_lowest !== undefined && data.pct_highest !== null;
    if (source === 'CADWR' && hasPctData) {
        html += '<div class="chart-container" style="margin-top:10px;">';
        html += '<div class="chart-title"><i class="fas fa-chart-bar" style="margin-right:8px;color:#FF9800;"></i>Historical Percentile Distribution</div>';
        html += '<div class="chart-area" id="pctChartArea"></div>';
        html += '</div>';
    }

    // Time series data
    var tsData = MapState.siteTimeSeries[siteNo];

    if (tsData && tsData.dates && tsData.dates.length > 0) {
        var values = tsData.values;
        var minVal = Math.min.apply(null, values);
        var maxVal = Math.max.apply(null, values);
        var avgVal = values.reduce(function(a, b) { return a + b; }, 0) / values.length;
        var change = values[values.length - 1] - values[0];

        // Stats cards
        html += '<div class="stats-grid">';
        html += '<div class="stat-card"><div class="stat-value">' + minVal.toFixed(1) + '</div><div class="stat-label">Min (ft)</div></div>';
        html += '<div class="stat-card"><div class="stat-value">' + maxVal.toFixed(1) + '</div><div class="stat-label">Max (ft)</div></div>';
        html += '<div class="stat-card"><div class="stat-value">' + avgVal.toFixed(1) + '</div><div class="stat-label">Avg (ft)</div></div>';
        html += '<div class="stat-card"><div class="stat-value" style="color:' + (change > 0 ? '#e53935' : '#43a047') + ';">' + (change > 0 ? '+' : '') + change.toFixed(1) + '</div><div class="stat-label">Change (ft)</div></div>';
        html += '</div>';

        // Chart - rendered with Plotly
        var chartTitle = source === 'CADWR' ? 'Groundwater Level History' : 'Water Level Depth - 10-day intervals';
        html += '<div class="chart-container">';
        html += '<div class="chart-title"><i class="fas fa-chart-line" style="margin-right:8px;color:' + sourceColor + ';"></i>' + chartTitle + '</div>';
        html += '<div class="chart-area" id="chartArea"></div>';
        html += '</div>';
    } else if (!hasPctData) {
        html += '<div style="margin-top:15px;padding:20px;background:#fff3cd;border-radius:8px;text-align:center;color:#856404;">';
        html += '<i class="fas fa-exclamation-triangle" style="margin-right:8px;"></i>No time series data available';
        html += '</div>';
    }

    body.innerHTML = html;
    overlay.style.display = 'block';
    popup.style.display = 'block';

    // Initialize popup position and size
    initPopupResize(popup);

    // Draw percentile chart with Plotly
    if (source === 'CADWR' && hasPctData) {
        setTimeout(function() { drawPercentileChart(data); }, 100);
    }

    // Draw time series chart with Plotly
    if (tsData && tsData.dates && tsData.dates.length > 0) {
        setTimeout(function() { drawTimeSeriesChart(tsData.dates, tsData.values, siteNo, sourceColor); }, 150);
    }
}

// Initialize popup resize functionality
function initPopupResize(popup) {
    // Set initial size and center position
    if (!popup.style.width) {
        popup.style.width = '750px';
    }
    if (!popup.style.height) {
        popup.style.height = 'auto';
    }

    // Center the popup
    var rect = popup.getBoundingClientRect();
    popup.style.left = (window.innerWidth - rect.width) / 2 + 'px';
    popup.style.top = Math.max(20, (window.innerHeight - rect.height) / 2) + 'px';

    // Add resize handles if not already present
    if (!popup.querySelector('.resize-handle')) {
        var handles = ['right', 'bottom', 'corner'];
        handles.forEach(function(pos) {
            var handle = document.createElement('div');
            handle.className = 'resize-handle ' + pos;
            handle.setAttribute('data-resize', pos);
            popup.appendChild(handle);
        });

        // Initialize resize events
        setupResizeEvents(popup);
    }
}

// Setup resize events
function setupResizeEvents(popup) {
    var isResizing = false;
    var currentHandle = null;
    var startX, startY, startWidth, startHeight;

    popup.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('resize-handle')) {
            isResizing = true;
            currentHandle = e.target.getAttribute('data-resize');
            startX = e.clientX;
            startY = e.clientY;
            startWidth = popup.offsetWidth;
            startHeight = popup.offsetHeight;
            e.preventDefault();
        }
    });

    document.addEventListener('mousemove', function(e) {
        if (!isResizing) return;

        var dx = e.clientX - startX;
        var dy = e.clientY - startY;

        if (currentHandle === 'right' || currentHandle === 'corner') {
            var newWidth = Math.max(400, startWidth + dx);
            popup.style.width = newWidth + 'px';
        }
        if (currentHandle === 'bottom' || currentHandle === 'corner') {
            var newHeight = Math.max(300, startHeight + dy);
            popup.style.height = newHeight + 'px';
        }

        // Relayout Plotly charts to fit new size
        var pctChart = document.getElementById('pctChartArea');
        var tsChart = document.getElementById('chartArea');
        if (pctChart && pctChart._fullLayout) {
            Plotly.relayout(pctChart, { autosize: true });
        }
        if (tsChart && tsChart._fullLayout) {
            Plotly.relayout(tsChart, { autosize: true });
        }
    });

    document.addEventListener('mouseup', function() {
        if (isResizing) {
            isResizing = false;
            currentHandle = null;
            // Final relayout
            var pctChart = document.getElementById('pctChartArea');
            var tsChart = document.getElementById('chartArea');
            if (pctChart && pctChart._fullLayout) {
                Plotly.Plots.resize(pctChart);
            }
            if (tsChart && tsChart._fullLayout) {
                Plotly.Plots.resize(tsChart);
            }
        }
    });
}

// Draw Percentile Chart
function drawPercentileChart(data) {
    var chartDiv = document.getElementById('pctChartArea');
    if (!chartDiv) return;

    var currentDepth = data.depth_ft;

    // Values sorted from shallowest (best) to deepest (worst) - reversed for Plotly horizontal bar
    var pctValues = [
        data.pct_highest,
        data.pct_90,
        data.pct_75,
        data.pct_50,
        data.pct_25,
        data.pct_10,
        data.pct_lowest
    ];
    var pctLabels = ['Highest', 'P90', 'P75', 'P50', 'P25', 'P10', 'Lowest'];
    var colors = ['#1565C0', '#1976D2', '#43A047', '#66BB6A', '#FFA726', '#F57C00', '#D32F2F'];

    var trace = {
        x: pctValues,
        y: pctLabels,
        type: 'bar',
        orientation: 'h',
        marker: { color: colors },
        text: pctValues.map(function(v) { return v !== null && v !== undefined ? v.toFixed(1) + ' ft' : ''; }),
        textposition: 'inside',
        textfont: { size: 9, color: 'white' },
        insidetextanchor: 'end',
        hovertemplate: '%{y}: %{x:.1f} ft depth<extra></extra>'
    };

    var pctClass = data.percentile_class || '';
    var classText = pctClass ? ' (' + pctClass + ')' : '';

    // Calculate x-axis range from data
    var validValues = pctValues.filter(function(v) { return v !== null && v !== undefined; });
    var minX = Math.min.apply(null, validValues);
    var maxX = Math.max.apply(null, validValues);
    if (currentDepth !== null && currentDepth !== undefined) {
        minX = Math.min(minX, currentDepth);
        maxX = Math.max(maxX, currentDepth);
    }
    var padding = (maxX - minX) * 0.15 || 5;

    // Build title with current depth info
    var titleText = 'Depth to Water (ft)';
    if (currentDepth !== null && currentDepth !== undefined) {
        titleText += '  |  <span style="color:#E91E63">Current: ' + currentDepth.toFixed(1) + ' ft</span>';
    }

    // Calculate height based on container width for proper aspect ratio
    var containerWidth = chartDiv.parentElement.offsetWidth - 10;
    var chartHeight = Math.max(160, Math.min(200, containerWidth * 0.28));

    var layout = {
        height: chartHeight,
        margin: { l: 60, r: 25, t: 10, b: 40 },
        xaxis: {
            title: { text: titleText, font: { size: 10 } },
            tickfont: { size: 9 },
            gridcolor: '#e0e0e0',
            range: [0, maxX * 1.15]
        },
        yaxis: {
            tickfont: { size: 9 },
            automargin: true
        },
        bargap: 0.15,
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        showlegend: false,
        // Current depth as vertical line shape
        shapes: (currentDepth !== null && currentDepth !== undefined) ? [{
            type: 'line',
            x0: currentDepth,
            x1: currentDepth,
            y0: 0,
            y1: 1,
            yref: 'paper',
            line: { color: '#E91E63', width: 3, dash: 'dash' }
        }] : []
    };

    Plotly.newPlot(chartDiv, [trace], layout, { responsive: true, displayModeBar: false }).then(function() {
        // Adjust container height to match chart
        var svg = chartDiv.querySelector('.main-svg');
        if (svg) {
            var svgHeight = svg.getAttribute('height');
            if (svgHeight) {
                chartDiv.style.height = svgHeight + 'px';
            }
        }
    });
}

// Draw Time Series Chart
function drawTimeSeriesChart(dates, values, siteNo, color) {
    var chartDiv = document.getElementById('chartArea');
    if (!chartDiv) return;

    color = color || '#1976D2';
    var rgbMatch = color.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
    var fillColor = rgbMatch ? 'rgba(' + parseInt(rgbMatch[1], 16) + ',' + parseInt(rgbMatch[2], 16) + ',' + parseInt(rgbMatch[3], 16) + ',0.1)' : 'rgba(25,118,210,0.1)';

    var trace = {
        x: dates,
        y: values,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Depth to Water',
        line: { color: color, width: 2 },
        marker: { size: 5, color: color },
        fill: 'tozeroy',
        fillcolor: fillColor
    };

    // Calculate height based on container width for proper aspect ratio
    var containerWidth = chartDiv.parentElement.offsetWidth - 10;
    var chartHeight = Math.max(180, Math.min(220, containerWidth * 0.32));

    var layout = {
        height: chartHeight,
        margin: { l: 55, r: 15, t: 10, b: 55 },
        xaxis: { title: 'Date', tickangle: -45, tickfont: { size: 8 }, gridcolor: '#e0e0e0' },
        yaxis: { title: 'Depth (ft)', titlefont: { size: 10 }, autorange: 'reversed', tickfont: { size: 8 }, gridcolor: '#e0e0e0' },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        hovermode: 'x unified'
    };

    var config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['pan2d', 'select2d', 'lasso2d', 'autoScale2d'],
        displaylogo: false
    };

    Plotly.newPlot(chartDiv, [trace], layout, config).then(function() {
        // Adjust container height to match chart
        var svg = chartDiv.querySelector('.main-svg');
        if (svg) {
            var svgHeight = svg.getAttribute('height');
            if (svgHeight) {
                chartDiv.style.height = svgHeight + 'px';
            }
        }
    });
}

// Close Marker Popup
function closeMarkerPopup() {
    document.getElementById('markerPopup').style.display = 'none';
    document.getElementById('popupOverlay').style.display = 'none';
}

// Update Scale Bar
function updateScaleBar(zoom, lat) {
    var metersPerPixel = 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, zoom);
    var scaleValues = [
        { meters: 5000000, label: '5000 km' },
        { meters: 2000000, label: '2000 km' },
        { meters: 1000000, label: '1000 km' },
        { meters: 500000, label: '500 km' },
        { meters: 200000, label: '200 km' },
        { meters: 100000, label: '100 km' },
        { meters: 50000, label: '50 km' },
        { meters: 20000, label: '20 km' },
        { meters: 10000, label: '10 km' },
        { meters: 5000, label: '5 km' },
        { meters: 2000, label: '2 km' },
        { meters: 1000, label: '1 km' },
        { meters: 500, label: '500 m' },
        { meters: 200, label: '200 m' },
        { meters: 100, label: '100 m' }
    ];

    var bestScale = scaleValues[0];
    for (var i = 0; i < scaleValues.length; i++) {
        var pixelWidth = scaleValues[i].meters / metersPerPixel;
        if (pixelWidth >= 50 && pixelWidth <= 150) {
            bestScale = scaleValues[i];
            break;
        }
        if (pixelWidth < 50) {
            bestScale = scaleValues[Math.max(0, i - 1)];
            break;
        }
    }

    var barWidth = bestScale.meters / metersPerPixel;
    document.getElementById('scaleBarLine').style.width = barWidth + 'px';
    document.getElementById('scaleBarLabel').textContent = bestScale.label;
}

// Initialize Map Events
function initMapEvents() {
    var gd = getPlotDiv();
    if (gd) {
        gd.on('plotly_click', function(data) {
            var point = data.points[0];
            if (point && point.customdata) {
                showMarkerPopup(point.customdata.site_no, point.customdata);
            }
        });

        gd.on('plotly_relayout', function(data) {
            if (data['map.zoom']) {
                MapState.currentZoom = data['map.zoom'];
            }
            var layout = gd.layout;
            if (layout && layout.map) {
                var zoom = layout.map.zoom || MapState.homeZoom;
                var center = layout.map.center || MapState.homeCenter;
                updateScaleBar(zoom, center.lat);
            }
        });
    }

    // ESC to close popup
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeMarkerPopup();
        }
    });

    // Initial scale bar
    setTimeout(function() {
        updateScaleBar(MapState.homeZoom, MapState.homeCenter.lat);
    }, 500);
}

// DOM Ready
document.addEventListener('DOMContentLoaded', initMapEvents);
