$(function () {
    let stopDonut, centralityBar;

    $('#runAnalysisV2').on('click', function () {
      alert('Advanced analysis initiated with selected parameters:\n' +
            'Location: ' + $('#locInputV2').val() + '\n' +
            'Coordinates: ' + $('#coordInputV2').val() + '\n' +
            'Centrality Measure: ' + $('#centralityType').val() + '\n' +
            'Stoppage Type: ' + $('#stoppageType').val());
      // Here I have added the logic to perform the analysis and updated the visualizations for dashboard v2.

      btn.prop('disabled', true).html('<i class="fas fa-sync fa-spin"></i> Running Calculations...');

      $.ajax({
        url: 'http://127.0.0.1:5000/analyze-advanced',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
          location: $('#locInputV2').val(),
          coordinates: $('#coordInputV2').val(),
          centrality: $('#centralityType').val(),
          stoppage: $('#stoppageType').val()
        }),
        success: function (response) {
          //  1. Update Maps
          $('#static-centrality-placeholder').html(`<img src="${res.static_centrality}" class="img-fluid">`);
          $('#interactive-centrality-container').html(res.interactive_centrality);

          // 2. Updating counts
          $('#bus-count').text(res.stop_counts.bus);
          $('#train-count').text(res.stop_counts.rail);
          $('#ferry-count').text(res.stop_counts.ferry);

          // 3. Updating Donuts
          if (stopDonut) stopDount.destroy();
          stopDonut = new Charts($('#dountStoppages').get(0).getContext('2d'),{
            type: 'doughnut',
            data: {
              labels: ['Bus', 'Train', 'Ferry'],
              datasets: [{
                data: [res.stop_count.bus, res.stop_count.rail, res.stop_count.ferry],
                backgroundColor: ['#007bff', '#28a745', '#ffc107']
              }]
            }
          });

          // 4. Updated Histogram
          if (centralityBar) centralityBar.destroy();
          centralityBar = new Chart($('#centralityHistogram').get(0).getContext('2d'), {
            type: 'bar',
            data: {
              labels: ['Degree', 'Closeness', 'Harmonic', 'Betweenness', 'Eigenvector', 'Load', 'Transport'],
              datasets: [{
                label: 'Score',
                backgroundColor: '#3c8dbc',
                data: res.histogram_data
              }]
            }
          });
        },
        error: function (xhr) {
          alert("Analysis failed: " + xhr.responseText);
        },
        complete: function () {
          btn.prop('disabled', false).text('Run Advanced Analysis');
        }
      });
    });
  });