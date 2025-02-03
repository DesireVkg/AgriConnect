document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('map')) {
        const map = L.map('map').setView([7.3697, 12.3547], 6); // Cameroon center
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Add product markers if they exist
        if (typeof products !== 'undefined') {
            products.forEach(product => {
                if (product.latitude && product.longitude) {
                    const marker = L.marker([product.latitude, product.longitude])
                        .addTo(map)
                        .bindPopup(`
                            <strong>${product.name}</strong><br>
                            Prix: ${product.price} FCFA<br>
                            <a href="/products/${product.id}">Voir détails</a>
                        `);
                }
            });
        }
        
        // Handle location picking for product creation
        if (document.getElementById('create-product-form')) {
            let selectedLocation = null;
            
            map.on('click', function(e) {
                if (selectedLocation) {
                    map.removeLayer(selectedLocation);
                }
                selectedLocation = L.marker(e.latlng).addTo(map);
                
                document.getElementById('latitude').value = e.latlng.lat;
                document.getElementById('longitude').value = e.latlng.lng;
            });
        }
    }
});
