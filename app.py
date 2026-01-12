import os
import io
import base64
import folium
import osmnx as ox
import networkx as nx
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend suitable for web servers

import matplotlib.pyplot as plt


app = Flask(__name__)
CORS(app) # Allows localhost:3000 to talk to localhost:5000

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False

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

@app.route('/analyze-network', methods=['POST'])
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

if __name__ == '__main__':
    app.run(port=5000, debug=True, use_reloader=False)