$(function () {
    // 1. Shared Chart Variables (Defined in outer scope to persist across button clicks)
    let donutNodesEdges, donutConnected, donutLengthType, donutIntersections, histogramRoadMetrics;

    const chartOptions = { 
        maintainAspectRatio: false, 
        responsive: true,
        plugins: {
            legend: { position: 'bottom' }
        }
    };

    // Helper Function to Update or Initialize All Charts
    function updateCharts(data) {
        // --- 1. Nodes vs Edges Donut ---
        if (donutNodesEdges) donutNodesEdges.destroy();
        donutNodesEdges = new Chart($('#donutNodesEdges').get(0).getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Nodes', 'Edges'],
                datasets: [{ 
                    data: [data.stats.n, data.stats.m], 
                    backgroundColor: ['#f56954', '#00a65a'] 
                }]
            },
            options: chartOptions
        });

        // --- 2. Connected Status Donut ---
        if (donutConnected) donutConnected.destroy();
        donutConnected = new Chart($('#donutConnected').get(0).getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Connected', 'Disconnected'],
                datasets: [{ 
                    data: [data.stats.connected_pct, 100 - data.stats.connected_pct], 
                    backgroundColor: ['#00c0ef', '#d2d6de'] 
                }]
            },
            options: chartOptions
        });

        // --- 3. Length by Type Donut ---
        if (donutLengthType) donutLengthType.destroy();
        donutLengthType = new Chart($('#donutLengthType').get(0).getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(data.stats.lengths_by_type),
                datasets: [{ 
                    data: Object.values(data.stats.lengths_by_type), 
                    backgroundColor: ['#f39c12', '#0073b7', '#3c8dbc', '#d81b60', '#39cccc'] 
                }]
            },
            options: chartOptions
        });

        // --- 4. Intersections vs Deadends Donut ---
        if (donutIntersections) donutIntersections.destroy();
        donutIntersections = new Chart($('#donutIntersections').get(0).getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Intersections', 'Deadends'],
                datasets: [{ 
                    data: [data.stats.intersection_count, data.stats.deadend_count], 
                    backgroundColor: ['#605ca8', '#ff851b'] 
                }]
            },
            options: chartOptions
        });

        // --- 5. Road Metrics Histogram ---
        if (histogramRoadMetrics) histogramRoadMetrics.destroy();
        histogramRoadMetrics = new Chart($('#histogramRoadMetrics').get(0).getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.histogram.labels,
                datasets: [{
                    label: 'Length (KM)',
                    backgroundColor: '#3c8dbc',
                    data: data.histogram.values
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { 
                    y: { 
                        beginAtZero: true,
                        title: { display: true, text: 'Kilometers (KM)' }
                    } 
                }
            }
        });
    }

    // 2. Main Action: The Analyze Button
    $('#analyzeBtn').on('click', function (e) {
        e.preventDefault(); // Prevent accidental form submission
        
        const btn = $(this);
        const locationVal = $('#locationInput').val();
        const coordsVal = $('#coordsInput').val();
        const netTypeVal = $('#networkType').val();

        // Validation
        if (!locationVal && !coordsVal) {
            alert("Please enter a Location Name OR Coordinates (Lat, Lon).");
            return;
        }

        // UI State: Loading
        btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Analyzing...');
        $('#static-map-placeholder').html('<div class="pt-5"><p class="text-muted">Contacting OpenStreetMap & generating graphs...</p></div>');

        // 3. AJAX Call to Flask
        $.ajax({
            url: '/analyze-network', // Fixed: Using relative path
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                location: locationVal,
                coords: coordsVal,
                network_type: netTypeVal
            }),
            success: function (response) {
                console.log("Success: Network data received.");

                // A. Update Statistics Table
                $('#stat-node-area').text(response.stats.area);
                $('#stat-edge-total').text(response.stats.edge_length_total + ' km');
                $('#stat-edge-avg').text(response.stats.edge_length_avg + ' m');
                $('#stat-streets-node').text(response.stats.streets_per_node_avg);
                $('#stat-intersections').text(response.stats.intersection_count);
                $('#stat-edge-density').text(response.stats.edge_density);
                $('#stat-clean-intersections').text(response.stats.clean_intersection_count);

                // B. Update Maps
                // Static Image
                $('#static-map-placeholder').html(`<img src="${response.static_map_url}" class="img-fluid" style="max-height: 400px;" alt="OSMnx Static Plot">`);
                // Interactive Folium Map
                $('#interactive-map-container').html(response.folium_html);

                // C. Redraw Charts
                updateCharts(response);
            },
            error: function (xhr) {
                // If Flask returns an error (500), display the message
                const errorMsg = xhr.responseJSON ? xhr.responseJSON.error : "Server is not responding.";
                alert("OSMnx Error: " + errorMsg);
                console.error("Traceback:", xhr.responseText);
            },
            complete: function () {
                // Reset Button State
                btn.prop('disabled', false).text('Generate Visualization');
            }
        });
    });
});