// static/js/push_manager.js

// Helper function to convert VAPID key
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

document.addEventListener('DOMContentLoaded', () => {
    const subscribeButton = document.getElementById('subscribe-button');
    const unsubscribeButton = document.getElementById('unsubscribe-button');
    const statusMessage = document.getElementById('push-status-message');
    const errorMessage = document.getElementById('push-error-message');
    const subscribedDeviceInfo = document.getElementById('subscribed-device-info');
    const currentSubscriptionDetails = document.getElementById('current-subscription-details');

    let swRegistration = null;
    let isSubscribed = false;

    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        statusMessage.textContent = 'Push messaging is not supported by your browser.';
        errorMessage.textContent = 'Please try a different browser for push notifications.';
        return;
    }

    // Register Service Worker (if not already - usually done globally)
    // Assuming your sw.js is at the root.
    navigator.serviceWorker.register('/sw.js') 
        .then(registration => {
            console.log('Service Worker registered with scope:', registration.scope);
            swRegistration = registration;
            initializeUI();
        })
        .catch(error => {
            console.error('Service Worker registration failed:', error);
            statusMessage.textContent = 'Service Worker registration failed.';
            errorMessage.textContent = `Error: ${error.message}`;
        });

    function initializeUI() {
        swRegistration.pushManager.getSubscription()
            .then(subscription => {
                isSubscribed = !(subscription === null);
                updateUI(subscription);
            });
    }

    function updateUI(subscription) {
        errorMessage.textContent = ''; // Clear previous errors
        if (subscription) {
            statusMessage.textContent = 'You are currently SUBSCRIBED to NWS Alert push notifications on this device.';
            subscribeButton.style.display = 'none';
            unsubscribeButton.style.display = 'block';
            subscribedDeviceInfo.style.display = 'block';
            currentSubscriptionDetails.textContent = JSON.stringify(subscription.toJSON(), null, 2);
        } else {
            statusMessage.textContent = 'You are currently NOT SUBSCRIBED to NWS Alert push notifications on this device.';
            subscribeButton.style.display = 'block';
            unsubscribeButton.style.display = 'none';
            subscribedDeviceInfo.style.display = 'none';
            currentSubscriptionDetails.textContent = '';
        }
    }

    subscribeButton.addEventListener('click', () => {
        subscribeButton.disabled = true;
        statusMessage.textContent = 'Subscribing...';
        errorMessage.textContent = '';

        Notification.requestPermission().then(permission => {
            if (permission !== 'granted') {
                statusMessage.textContent = 'Push notification permission was not granted.';
                errorMessage.textContent = 'Please enable notifications in your browser settings for this site.';
                subscribeButton.disabled = false;
                return;
            }

            const applicationServerKey = urlBase64ToUint8Array(VAPID_PUBLIC_KEY);
            swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            })
            .then(subscription => {
                console.log('User is subscribed:', subscription);
                return sendSubscriptionToServer(subscription, 'POST'); // Send to your save endpoint
            })
            .then(responseJson => {
                 if (responseJson && responseJson.status === 'success') {
                    statusMessage.textContent = 'Successfully subscribed! You will now receive NWS alerts.';
                    isSubscribed = true;
                    swRegistration.pushManager.getSubscription().then(sub => updateUI(sub)); // Refresh UI
                } else {
                    statusMessage.textContent = 'Subscription attempt partly failed on server.';
                    errorMessage.textContent = responseJson ? responseJson.message : 'Unknown server error.';
                    // If server fails, try to unsubscribe to clean up inconsistent state
                    swRegistration.pushManager.getSubscription().then(sub => { if(sub) sub.unsubscribe(); });
                }
            })
            .catch(err => {
                console.error('Failed to subscribe the user: ', err);
                statusMessage.textContent = 'Subscription failed.';
                errorMessage.textContent = `Error: ${err.message}`;
            })
            .finally(() => {
                subscribeButton.disabled = false;
            });
        });
    });

    unsubscribeButton.addEventListener('click', () => {
        unsubscribeButton.disabled = true;
        statusMessage.textContent = 'Unsubscribing...';
        errorMessage.textContent = '';

        swRegistration.pushManager.getSubscription()
            .then(subscription => {
                if (subscription) {
                    return subscription.unsubscribe()
                        .then(successful => {
                            if (successful) {
                                console.log('User unsubscribed from browser.');
                                // Send endpoint to server to delete/deactivate
                                return sendSubscriptionToServer(subscription.toJSON(), 'DELETE'); 
                            } else {
                                throw new Error('Browser unsubscription failed.');
                            }
                        });
                } else {
                    // Already unsubscribed or no subscription found
                    return Promise.resolve({status: 'success', message: 'No active subscription found in browser.'});
                }
            })
            .then(responseJson => {
                if (responseJson && responseJson.status === 'success') {
                    statusMessage.textContent = 'Successfully unsubscribed.';
                    isSubscribed = false;
                    updateUI(null); // Update UI to reflect unsubscription
                } else {
                    statusMessage.textContent = 'Unsubscription attempt partly failed on server.';
                    errorMessage.textContent = responseJson ? responseJson.message : 'Unknown server error.';
                    // UI might be out of sync if server fails but browser unsubscribed
                }
            })
            .catch(err => {
                console.error('Error unsubscribing: ', err);
                statusMessage.textContent = 'Unsubscription failed.';
                errorMessage.textContent = `Error: ${err.message}`;
            })
            .finally(() => {
                unsubscribeButton.disabled = false;
            });
    });

    function sendSubscriptionToServer(subscriptionData, httpMethod) {
        const url = (httpMethod === 'POST') ? SAVE_SUBSCRIPTION_URL : DELETE_SUBSCRIPTION_URL;
        const bodyPayload = (httpMethod === 'POST') 
            ? JSON.stringify(subscriptionData.toJSON()) // For POST, send full sub object
            : JSON.stringify({ endpoint: subscriptionData.endpoint }); // For DELETE, just endpoint might be enough

        return fetch(url, {
            method: httpMethod,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') // Important for Django POST/DELETE
            },
            body: bodyPayload
        })
        .then(response => {
            if (!response.ok) {
                // Try to get error message from server if JSON, otherwise use status text
                return response.json().catch(() => null).then(errData => {
                    throw new Error(errData ? errData.message : `Server error: ${response.status} ${response.statusText}`);
                });
            }
            return response.json();
        })
        .catch(error => {
            console.error('Error sending subscription to server:', error);
            errorMessage.textContent = `Server communication error: ${error.message}`;
            // Return an object that indicates failure to the calling promise chain
            return { status: 'error', message: error.message }; 
        });
    }

    // Helper function to get CSRF token from cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
