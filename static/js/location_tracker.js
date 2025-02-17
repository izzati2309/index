class LocationTracker {
    constructor() {
        this.watchId = null;
        this.lastPosition = null;
        this.accuracyThresholds = {
            initial: 100,    // More lenient initial threshold
            indoor: {
                warning: 50,
                max: 100,
                movement: 3,
                updateInterval: 3000
            },
            outdoor: {
                warning: 30,
                max: 50,
                movement: 5,
                updateInterval: 5000
            }
        };
        this.minMovementThreshold = 5; // 5 meters minimum movement
        this.updateInterval = 5000; // 5 seconds
        this.lastUpdateTime = null;
        this.shahAlamBounds = {
            minLat: 2.9,
            maxLat: 3.2,
            minLng: 101.4,
            maxLng: 101.7
        };

         // Initialize environment detection
         this.detectEnvironment();
    }

    async detectEnvironment() {
        if ('permissions' in navigator) {
            try {
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, {
                        enableHighAccuracy: true,
                        timeout: 5000,
                        maximumAge: 0
                    });
                });
                
                const accuracy = position.coords.accuracy;
                this.isIndoor = accuracy > this.accuracyThresholds.outdoor.max;
                this.updateThresholds();
                
                console.log(`Environment detected: ${this.isIndoor ? 'Indoor' : 'Outdoor'}`);
            } catch (error) {
                console.warn('Environment detection failed:', error);
                this.isIndoor = false;
            }
        }
    }

    updateThresholds() {
        const current = this.isIndoor ? 
            this.accuracyThresholds.indoor : 
            this.accuracyThresholds.outdoor;
            
        this.accuracyThreshold = current.max;
        this.minMovementThreshold = current.movement;
        this.updateInterval = current.updateInterval;
    }

    startTracking() {
        if ("geolocation" in navigator) {
            // Get initial position
            this.getInitialPosition();

            // Start watching position
            this.watchId = navigator.geolocation.watchPosition(
                this.handleSuccess.bind(this),
                this.handleError.bind(this),
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );

            console.log('Location tracking started');
            return true;
        } else {
            console.error("Geolocation is not supported by this browser.");
            return false;
        }
    }

    stopTracking() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
            this.lastPosition = null;
            this.lastUpdateTime = null;
            console.log('Location tracking stopped');
            return true;
        }
        return false;
    }

    updateLocationStatus(type, message) {
        const locationStatus = document.getElementById('locationStatus');
        if (locationStatus) {
            locationStatus.textContent = message;
            switch(type) {
                case 'success':
                    locationStatus.style.backgroundColor = '#28a745';
                    break;
                case 'warning':
                    locationStatus.style.backgroundColor = '#ffc107';
                    break;
                case 'error':
                    locationStatus.style.backgroundColor = '#dc3545';
                    break;
            }
        }
    }

    getInitialPosition() {
        let retryCount = 0;
        const maxRetries = 3;
    
        const tryPosition = () => {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const accuracy = position.coords.accuracy;
                    
                    // Always proceed with tracking, just show different status messages
                    if (accuracy > this.accuracyThresholds.initial) {
                        // Still start tracking but warn about accuracy
                        this.updateLocationStatus('warning', 
                            `Location tracking active (${Math.round(accuracy)}m accuracy)`);
                    } else {
                        this.updateLocationStatus('success', 
                            `Location tracking active (${Math.round(accuracy)}m accuracy)`);
                    }
                    
                    // Always handle the position regardless of accuracy
                    this.handleSuccess(position);
                    
                },
                (error) => {
                    if (retryCount < maxRetries) {
                        retryCount++;
                        this.updateLocationStatus('warning', 
                            `Acquiring GPS signal (attempt ${retryCount}/${maxRetries})...`);
                        setTimeout(tryPosition, 2000);
                    } else {
                        this.handleError(error);
                    }
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        };
    
        tryPosition();
    }

    isValidLocation(lat, lng, accuracy) {
        // Check if accuracy is within threshold
        if (accuracy > this.accuracyThreshold) {
            console.log(`Location accuracy (${accuracy}m) exceeds threshold`);
            return true; // Still accept but log it
        }

        const inBounds = lat >= this.shahAlamBounds.minLat && 
                        lat <= this.shahAlamBounds.maxLat && 
                        lng >= this.shahAlamBounds.minLng && 
                        lng <= this.shahAlamBounds.maxLng;

        if (!inBounds) {
            console.log('Location outside Shah Alam bounds');
        }

        return inBounds;
    }

    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371e3; // Earth's radius in meters
        const φ1 = lat1 * Math.PI/180;
        const φ2 = lat2 * Math.PI/180;
        const Δφ = (lat2-lat1) * Math.PI/180;
        const Δλ = (lon2-lon1) * Math.PI/180;

        const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                Math.cos(φ1) * Math.cos(φ2) *
                Math.sin(Δλ/2) * Math.sin(Δλ/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

        return R * c; // Distance in meters
    }

    async handleSuccess(position) {
        try {
            const currentTime = Date.now();
            
            // Check update interval
            if (this.lastUpdateTime && (currentTime - this.lastUpdateTime) < this.updateInterval) {
                return;
            }

            const accuracy = position.coords.accuracy;
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            // Update environment if accuracy changes significantly
            if (Math.abs(accuracy - (this.lastPosition?.accuracy || 0)) > 10) {
                const newIsIndoor = accuracy > this.accuracyThresholds.outdoor.max;
                if (this.isIndoor !== newIsIndoor) {
                    this.isIndoor = newIsIndoor;
                    this.updateThresholds();
                    this.updateLocationStatus('warning', 
                        `Switched to ${this.isIndoor ? 'indoor' : 'outdoor'} mode (${Math.round(accuracy)}m accuracy)`);
                }
            }

            // Check if location is valid
            if (!this.isValidLocation(lat, lng, accuracy)) {
                return;
            }

            // Check minimum movement threshold
            if (this.lastPosition) {
                const distance = this.calculateDistance(
                    this.lastPosition.lat,
                    this.lastPosition.lng,
                    lat,
                    lng
                );

                if (distance < this.minMovementThreshold) {
                    console.log(`Movement (${distance}m) below threshold`);
                    return;
                }
            }

            // Prepare location data
            const locationData = {
                lat: lat,
                lng: lng,
                accuracy: accuracy,
                timestamp: new Date().toISOString(),
                speed: position.coords.speed || 0,
                isIndoor: this.isIndoor
            };

            // Send update to server
            const response = await fetch('/update_driver_location', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(locationData)
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            if (data.status === 'success') {
                // Update last position and time
                this.lastPosition = { lat, lng, accuracy };
                this.lastUpdateTime = currentTime;

                // Update UI elements
                this.updateUI(locationData);
                console.log('Location updated successfully:', locationData);
            }

        } catch (error) {
            console.error('Error in handleSuccess:', error);
            this.handleError(error);
        }
    }

    updateUI(locationData) {
        // Update accuracy display
        const accuracyElement = document.getElementById('accuracyDisplay');
        if (accuracyElement) {
            const accuracyClass = locationData.accuracy <= this.accuracyThresholds.outdoor.warning ? 'good' : 
                                locationData.accuracy <= this.accuracyThresholds.outdoor.max ? 'medium' : 'poor';
            accuracyElement.textContent = `Accuracy: ${Math.round(locationData.accuracy)}m (${accuracyClass})`;
            accuracyElement.className = `accuracy-${accuracyClass}`;
        }

        // Update last update time
        const lastUpdateElement = document.getElementById('lastUpdate');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = new Date().toLocaleString();
        }

        // Update location status
        const locationStatus = document.getElementById('locationStatus');
        if (locationStatus) {
            locationStatus.textContent = 'Location tracking active';
            locationStatus.style.backgroundColor = '#28a745';
        }
    }

    handleError(error) {
        let errorMessage = 'Error getting location: ';
        
        switch(error.code) {
            case error.PERMISSION_DENIED:
                errorMessage += 'Location permission denied.';
                break;
            case error.POSITION_UNAVAILABLE:
                errorMessage += 'Location information unavailable.';
                break;
            case error.TIMEOUT:
                errorMessage += 'Location request timed out.';
                break;
            default:
                errorMessage += error.message || 'Unknown error occurred.';
        }

        console.error(errorMessage);

        // Update UI elements
        const errorDisplay = document.getElementById('locationError');
        if (errorDisplay) {
            errorDisplay.textContent = errorMessage;
            errorDisplay.style.display = 'block';
            setTimeout(() => {
                errorDisplay.style.display = 'none';
            }, 5000);
        }

        // Update location status
        const locationStatus = document.getElementById('locationStatus');
        if (locationStatus) {
            locationStatus.textContent = 'Location tracking error';
            locationStatus.style.backgroundColor = '#dc3545';
        }

        // Retry connection after error
        if (this.watchId === null) {
            console.log('Retrying location tracking in 5 seconds...');
            setTimeout(() => {
                this.startTracking();
            }, 5000);
        }
    }
}