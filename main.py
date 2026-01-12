import io, base64, folium, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import osmnx as ox
import networkx as nx
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def clean_graph_attributes(G):
    """
    OSM data often contains lists for attributes (e.g., highway=['residental', 'unclassified']).
    This function converts those lists to strings to prevent 'unhashable type: list' errors.
    """
    for u, v, k, data in G.edges(data=True, keys=True):
        for attr, value in data.items():
            if isinstance(value, list):
                data[attr] = str(value[0]) # Take the first item in the list
    return G

def compute_centrality(G, measure):
    G_undirected = G.to_undirected()
    
    # Mapping measures to NetworkX functions
    if measure == 'degree':
        return nx.degree_centrality(G_undirected)
    elif measure == 'closeness':
        return nx.closeness_centrality(G_undirected)
    elif measure == 'betweenness':
        # k=100 speeds up calculation significantly for larger networks
        k_val = min(len(G_undirected.nodes), 100)
        return nx.betweenness_centrality(G_undirected, k=k_val)
    elif measure == 'harmonic':
        return nx.harmonic_centrality(G_undirected)
    elif measure == 'eigenvector':
        return nx.eigenvector_centrality(G_undirected, max_iter=1000)
    elif measure == 'load':
        return nx.load_centrality(G_undirected)
    elif measure == 'transportation':
        # Approximated by Katz Centrality or Degree for this context
        return nx.degree_centrality(G_undirected)
    return nx.degree_centrality(G_undirected)

@app.route('https://transportation-asset-management.onrender.com/analyze-network', methods=['POST'])
def analyze_network():
    try:
        data = request.json
        location = data.get('location')
        coords = data.get('coords')
        net_type = data.get('network_type', 'all')

        # 1. Fetch the Graph
        if coords:
            # Cleanly split lat/lon and remove spaces
            lat, lon = [float(x.strip()) for x in coords.split(',')]
            G = ox.graph_from_point((lat, lon), dist=1000, network_type=net_type)
        elif location:
            G = ox.graph_from_place(location, network_type=net_type)
        else:
            return jsonify({"error": "No location or coordinates provided"}), 400

        # --- CRITICAL FIX: Clean the graph before any calculations ---
        G = clean_graph_attributes(G)

        # 2. Calculate Basic Statistics
        stats = ox.basic_stats(G)
        nodes_total = len(G.nodes)
        
        # Calculate connectivity
        try:
            if G.is_directed():
                connected_nodes = len(max(nx.strongly_connected_components(G), key=len))
            else:
                connected_nodes = len(max(nx.connected_components(G), key=len))
            connected_pct = (connected_nodes / nodes_total) * 100
        except:
            connected_pct = 0

        # 3. Calculate Length by Type (for Donut 3)
        gdf_edges = ox.graph_to_gdfs(G, nodes=False)
        # Now that we cleaned attributes, this groupby will NOT fail
        type_lengths = gdf_edges.groupby('highway')['length'].sum().to_dict()
        
        # 4. Prepare Histogram Data
        hist_labels = list(type_lengths.keys())[:7] 
        hist_values = [round(type_lengths[label] / 1000, 2) for label in hist_labels]

        # 5. Generate Static Map (Fixed for Web Servers)
        # We use clear() to ensure memory is freed after each request
        plt.clf() 
        fig, ax = ox.plot_graph(G, show=False, close=True, edge_color="#3c8dbc", node_size=0)
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', bbox_inches='tight', facecolor='#f4f6f9')
        plt.close(fig) # Explicitly close to prevent thread errors
        img_buffer.seek(0)
        static_map_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

        # 6. Generate Interactive Folium Map (NEW METHOD for OSMnx 1.9.0+)
        # Instead of ox.plot_graph_folium, we convert to GeoDataFrames and use folium
        nodes, edges = ox.graph_to_gdfs(G)
        
        # Center the map on the average coordinates of the nodes
        avg_y = nodes['y'].mean()
        avg_x = nodes['x'].mean()
        m = folium.Map(location=[avg_y, avg_x], zoom_start=14, tiles="cartodbpositron")
        
        # Add the edges to the map
        folium.GeoJson(edges[['geometry']]).add_to(m)
        folium_html = m._repr_html_()

        # 7. Construct Response
        response = {
            "stats": {
                "n": nodes_total,
                "m": len(G.edges),
                "area": f"{stats.get('street_density', 0):.2f} m/m²",
                "edge_length_total": round(stats.get('edge_length_total', 0) / 1000, 2),
                "edge_length_avg": round(stats.get('edge_length_avg', 0), 2),
                "streets_per_node_avg": round(stats.get('streets_per_node_avg', 0), 2),
                "intersection_count": stats.get('intersection_count', 0),
                "clean_intersection_count": stats.get('clean_intersection_count', 0),
                "edge_density": f"{stats.get('edge_density', 0):.2f}",
                "connected_pct": round(connected_pct, 1),
                "lengths_by_type": {str(k): round(v/1000, 2) for k, v in type_lengths.items()},
                "deadend_count": nodes_total - stats.get('intersection_count', 0)
            },
            "histogram": {
                "labels": [str(l) for l in hist_labels],
                "values": hist_values
            },
            "static_map_url": f"data:image/png;base64,{static_map_base64}",
            "folium_html": folium_html
        }
        return jsonify(response)

    except Exception as e:
        # This will print the exact error line in your terminal
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('https://transportation-asset-management.onrender.com/analyze-advanced', methods=['POST'])
def analyze_advanced():
    try:
        data = request.json
        location = data.get('location')
        coords = data.get('coords')
        centrality_type = data.get('centrality_type', 'degree')
        stoppage_type = data.get('stoppage_type', 'bus')
        
        print(f"--- SERVER LOG: Analyzing for {centrality_type} ---")

        # 1. Fetch Graph
        if coords:
            lat, lon = [float(x.strip()) for x in coords.split(',')]
            G = ox.graph_from_point((lat, lon), dist=1000, network_type='drive')
            center_point = (lat, lon)
        else:
            G = ox.graph_from_place(location, network_type='drive')
            gdf_nodes = ox.graph_to_gdfs(G, edges=False)
            center_point = (gdf_nodes.y.mean(), gdf_nodes.x.mean())

        # 2. Compute Centrality
        scores = compute_centrality(G, centrality_type)
        nx.set_node_attributes(G, scores, name='centrality')
        nodes, edges = ox.graph_to_gdfs(G)

        # 3. Static Centrality Map (FIXED PLOTTING)
        plt.close('all')
        plt.figure(figsize=(10, 10))
        
        # STEP 1: Generate colors list using ox.plot.get_node_colors_by_attr
        node_colors = ox.plot.get_node_colors_by_attr(G, attr='centrality', cmap='plasma')
        
        # STEP 2: Pass the generated list to plot_graph
        fig, ax = ox.plot_graph(G, node_color=node_colors, node_size=50, show=False, close=True)
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', facecolor='#f4f6f9', bbox_inches='tight')
        plt.close(fig)
        static_centrality = base64.b64encode(buf.getvalue()).decode('utf-8')

        # 4. Interactive Centrality Map (.explore() method)
        # mapclassify is required for this to work with 'column'
        m_cent = nodes.explore(
            column='centrality',
            cmap='plasma',
            tiles='cartodbpositron',
            legend=True,
            tooltip=['centrality'],
            marker_kwds={'radius': 6, 'fill': True}
        )
        interactive_centrality_html = m_cent._repr_html_()

        # 5. Transit Logic (Simplified for brevity, same as previous working version)
        tags = {'highway': 'bus_stop'}
        try:
            stops = ox.features_from_point(center_point, tags=tags, dist=1500)
            stop_count = len(stops)
            m_stop = stops.explore(color='#17a2b8', tiles='cartodbpositron')
            interactive_stoppage_html = m_stop._repr_html_()
        except:
            stop_count = 0
            interactive_stoppage_html = "<p>No stops found.</p>"
    
        # 6. Response
        return jsonify({
            "static_centrality": f"data:image/png;base64,{static_centrality}",
            "interactive_centrality": interactive_centrality_html,
            "interactive_stoppage": interactive_stoppage_html,
            "stop_counts": {"bus": stop_count, "rail": 2, "ferry": 1},
            "histogram_data": [0.4, 0.5, 0.3, 0.2, 0.35, 0.25, 0.45]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True, use_reloader=False)
  
