// Initialize the map
var map = L.map('map').setView([3.0730, 101.5190], 13);  // Set initial view to UiTM Shah Alam

// Add OpenStreetMap tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// Function to add bus markers to the map
function addBusMarkers(busLocations) {
    // Clear existing markers
    map.eachLayer(function (layer) {
        if (layer instanceof L.Marker) {
            map.removeLayer(layer);
        }
    });

    // Add new markers
    for (var route in busLocations) {
        for (var bus in busLocations[route]) {
            var location = busLocations[route][bus];
            var marker = L.marker([location.lat, location.lng]).addTo(map);
            marker.bindPopup("Route " + route + ": " + bus + " at " + location.stop);
        }
    }
}

// Function to update bus locations
function updateBusLocations() {
    fetch('/update_bus_locations')
        .then(response => response.json())
        .then(data => {
            addBusMarkers(data);
        })
        .catch(error => console.error('Error:', error));
}

// Update bus locations every 30 seconds
setInterval(updateBusLocations, 30000);

// Initial update
updateBusLocations();

