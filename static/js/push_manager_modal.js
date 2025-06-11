// static/js/push_manager_modal.js



// Helper function to convert VAPID public key string to Uint8Array
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

// Helper function to get CSRF token from cookies (Django standard)
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}



// iOS Detection Helper Functions
function isIOS() {
    return [
        'iPad Simulator', 'iPhone Simulator', 'iPod Simulator', 'iPad', 'iPhone', 'iPod'
    ].includes(navigator.platform)
        // Also, iPad on iOS 13+ reports as "MacIntel" but acts like iOS for PWA features
        || (navigator.userAgent.includes("Mac") && "ontouchend" in document);
}

function isStandalonePWA() {
    // Checks if the PWA is running in standalone mode (i.e., added to Home Screen)
    return window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
}

document.addEventListener('DOMContentLoaded', () => {

    const pushModalElement = document.getElementById('pushNotificationModal');
    console.log("PUSH_MODAL_JS: pushModalElement:", pushModalElement); // Check if modal itself is found

    const subscribeButton = document.getElementById('subscribe-button-modal');
    console.log("PUSH_MODAL_JS: subscribeButton:", subscribeButton); // Will be null if not found

    const unsubscribeButton = document.getElementById('unsubscribe-button-modal');
    console.log("PUSH_MODAL_JS: unsubscribeButton:", unsubscribeButton);

    const statusMessage = document.getElementById('push-status-message-modal');
    console.log("PUSH_MODAL_JS: statusMessage:", statusMessage);

    const errorMessage = document.getElementById('push-error-message-modal');
    console.log("PUSH_MODAL_JS: errorMessage:", errorMessage);

    const iosInstructionsModal = document.getElementById('ios-instructions-modal');
    console.log("PUSH_MODAL_JS: iosInstructionsModal:", iosInstructionsModal);


    // Add checks to see if these elements were found:
    if (!subscribeButton) console.warn("PUSH_MODAL_JS: #subscribe-button-modal not found!");
    if (!unsubscribeButton) console.warn("PUSH_MODAL_JS: #unsubscribe-button-modal not found!");
    if (!statusMessage) console.warn("PUSH_MODAL_JS: #push-status-message-modal not found!");
    if (!errorMessage) console.warn("PUSH_MODAL_JS: #push-error-message-modal not found!");
    if (!iosInstructionsModal) console.warn("PUSH_MODAL_JS: #ios-instructions-modal not found!");

 
    console.log("PUSH_MODAL_JS: DOMContentLoaded - Script starting."); // Add this to confirm entry

    //const pushModalElement = document.getElementById('pushNotificationModal'); // Get the modal itself

    if (!pushModalElement) {
        console.warn('PUSH_MODAL_JS: Modal element #pushNotificationModal not found.');
        return;
    }
    console.log("PUSH_MODAL_JS: Modal element #pushNotificationModal found.");

    // Use the '-modal' suffixed IDs



    if (!pushModalElement) {
        // console.warn('Push notification modal element (#pushNotificationModal) not found on this page.');
        return; // Exit if the modal isn't on the current page
    }

    // Get elements from INSIDE the modal by their specific IDs
    //const subscribeButton = document.getElementById('subscribe-button');
    //const unsubscribeButton = document.getElementById('unsubscribe-button');
    //const statusMessage = document.getElementById('push-status-message');
    //const errorMessage = document.getElementById('push-error-message');
    //const iosInstructionsModal = document.getElementById('ios-instructions');
    // const subscribedDeviceInfo = document.getElementById('subscribed-device-info-modal'); // Optional
    // const currentSubscriptionDetails = document.getElementById('current-subscription-details-modal'); // Optional

    let swRegistration = null; // Service Worker registration
    let isSubscribed = false;  // Current subscription state for this browser

    // Check for browser support and if VAPID_PUBLIC_KEY is defined (should be by the template)
    const generalPushSupport = 'serviceWorker' in navigator && 'PushManager' in window && Notification;
    if (!generalPushSupport || typeof VAPID_PUBLIC_KEY === 'undefined' || VAPID_PUBLIC_KEY === '') {
        if (statusMessage) statusMessage.textContent = 'Push messaging is not supported by your browser or essential configuration is missing from the site.';
        if (subscribeButton) subscribeButton.style.display = 'none';
        if (unsubscribeButton) unsubscribeButton.style.display = 'none';
        if (iosInstructionsModal) iosInstructionsModal.style.display = 'none';
        console.warn('Push notifications not supported by browser, or VAPID_PUBLIC_KEY global JS variable is missing/empty.');
        return;
    }

    function updateModalUI(subscriptionObject) {
        if (errorMessage) errorMessage.textContent = ''; // Clear previous errors
        console.log("updatemodalUI");
        const onIOSDevice = isIOS();
        const runningStandalone = isStandalonePWA();

        if (onIOSDevice && !runningStandalone && generalPushSupport) {
            // On iOS Safari (not added to Home Screen PWA), but push *might* be technically supported by browser version
            if (statusMessage) statusMessage.textContent = 'To enable alerts on iOS, please add this app to your Home Screen first.';
            if (iosInstructionsModal) iosInstructionsModal.style.display = 'block';
            if (subscribeButton) { subscribeButton.style.display = 'block'; subscribeButton.disabled = true; } // Show but disable
            if (unsubscribeButton) { unsubscribeButton.style.display = 'none'; unsubscribeButton.disabled = true; }
        } else if (generalPushSupport) {
            // Not iOS, OR iOS PWA (standalone), OR browser that supports push directly
            if (iosInstructionsModal) iosInstructionsModal.style.display = 'none';

            if (subscriptionObject) {
                isSubscribed = true;
                if (statusMessage) statusMessage.textContent = 'You are SUBSCRIBED to NWS Alert push notifications on this device.';
                if (subscribeButton) subscribeButton.style.display = 'none';
                if (unsubscribeButton) unsubscribeButton.style.display = 'block';
                // if (subscribedDeviceInfo) subscribedDeviceInfo.style.display = 'block'; // Optional for showing details
                // if (currentSubscriptionDetails) currentSubscriptionDetails.textContent = JSON.stringify(subscriptionObject.toJSON(), null, 2);
            } else {
                isSubscribed = false;
                if (statusMessage) statusMessage.textContent = 'You are NOT SUBSCRIBED to NWS Alert push notifications on this device.';
                if (subscribeButton) subscribeButton.style.display = 'block';
                if (unsubscribeButton) unsubscribeButton.style.display = 'none';
                // if (subscribedDeviceInfo) subscribedDeviceInfo.style.display = 'none'; // Optional
                // if (currentSubscriptionDetails) currentSubscriptionDetails.textContent = '';
            }
            if (subscribeButton) subscribeButton.disabled = false;
            if (unsubscribeButton) unsubscribeButton.disabled = false;
        } else {
            // Fallback if general push support was initially true but something else changed
            if (statusMessage) statusMessage.textContent = 'Push messaging is not available.';
            if (subscribeButton) subscribeButton.style.display = 'none';
            if (unsubscribeButton) unsubscribeButton.style.display = 'none';
            if (iosInstructionsModal) iosInstructionsModal.style.display = 'none';
        }
    }

    function initializePushUIState() {
        if (!swRegistration) {
            if (statusMessage) statusMessage.textContent = 'Service worker not ready. Cannot check subscription.';
            console.error('Service worker registration not available for UI initialization.');
            return;
        }
        if (statusMessage) statusMessage.textContent = 'Checking subscription status...';
        console.log("status message");
        swRegistration.pushManager.getSubscription()
            .then(subscription => {
                updateModalUI(subscription);
            })
            .catch(err => {
                console.error('Error getting current push subscription state:', err);
                if (statusMessage) statusMessage.textContent = 'Could not get subscription status.';
                if (errorMessage) errorMessage.textContent = `Error: ${err.message}`;
                updateModalUI(null);
            });
    }

    // Get Service Worker registration. This assumes sw.js is at the root of your site.
    navigator.serviceWorker.register('/sw.js')
        .then(registration => {
            swRegistration = registration;
            console.log('Service Worker is registered for push management (modal). Scope:', swRegistration.scope);
            // Listen for the Bootstrap modal 'shown' event to initialize/refresh UI state
            pushModalElement.addEventListener('shown.bs.modal', () => {
                console.log('Push notification modal shown. Initializing/refreshing UI state.');
                initializePushUIState();
            });
            // Initialize UI when modal might already be open or for the first time if page directly has modal logic
            if (bootstrap.Modal.getInstance(pushModalElement)) { // Check if modal is already initialized by Bootstrap
                initializePushUIState(); // Check state if modal is already known to Bootstrap
            }

        })
        .catch(error => {
            console.error('Service Worker not ready for push management (modal):', error);
            if (statusMessage) statusMessage.textContent = 'Service Worker could not be registered.';
            if (errorMessage) errorMessage.textContent = `Error: ${error.message}`;
        });

    if (subscribeButton) {
        subscribeButton.addEventListener('click', () => {
            subscribeButton.disabled = true;
            if (statusMessage) statusMessage.textContent = 'Subscribing... Please wait.';
            if (errorMessage) errorMessage.textContent = '';
            console.log("subed");
            Notification.requestPermission().then(permissionResult => {
                if (permissionResult !== 'granted') {
                    if (statusMessage) statusMessage.textContent = 'Push notification permission was not granted.';
                    if (errorMessage) errorMessage.textContent = 'To subscribe, please enable notifications for this site in your browser settings.';
                    subscribeButton.disabled = false;
                    return;
                }

                console.log('Notification permission granted. Subscribing with PushManager...');
                const applicationServerKey = urlBase64ToUint8Array(VAPID_PUBLIC_KEY);
                swRegistration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: applicationServerKey
                })
                    .then(subscription => {
                        console.log('User subscribed with PushManager:', subscription);
                        if (statusMessage) statusMessage.textContent = 'Subscription request sent to browser. Saving to server...';
                        return sendSubscriptionToServer(subscription.toJSON(), 'POST', SAVE_SUBSCRIPTION_URL);
                    })
                    .then(responseJson => {
                        if (responseJson && responseJson.status === 'success') {
                            console.log('Subscription saved on server.');
                            // statusMessage will be updated by initializePushUIState via modal event or direct call
                            initializePushUIState(); // Re-check and update UI
                        } else {
                            console.error('Server failed to save subscription:', responseJson);
                            if (statusMessage) statusMessage.textContent = 'Subscription failed on server.';
                            if (errorMessage) errorMessage.textContent = responseJson ? responseJson.message : 'Unknown server error while saving.';
                            // If server save fails, unsubscribe from browser to keep state consistent
                            swRegistration.pushManager.getSubscription().then(sub => {
                                if (sub) sub.unsubscribe().then(() => initializePushUIState());
                                else initializePushUIState();
                            });
                        }
                    })
                    .catch(err => {
                        console.error('Failed to subscribe the user: ', err);
                        if (statusMessage) statusMessage.textContent = 'Subscription failed.';
                        if (errorMessage) errorMessage.textContent = `Error: ${err.message}`;
                        subscribeButton.disabled = false;
                    });
            });
        });
    } else {
        console.warn('Subscribe button (#subscribe-button-modal) not found.');
    }



    if (unsubscribeButton) {
        unsubscribeButton.addEventListener('click', () => {
            unsubscribeButton.disabled = true;
            if (statusMessage) statusMessage.textContent = 'Unsubscribing... Please wait.';
            if (errorMessage) errorMessage.textContent = '';

            swRegistration.pushManager.getSubscription()
                .then(subscription => {
                    if (subscription) {
                        return subscription.unsubscribe()
                            .then(successful => {
                                if (successful) {
                                    console.log('User unsubscribed from browser.');
                                    return sendSubscriptionToServer({ endpoint: subscription.endpoint }, 'POST', DELETE_SUBSCRIPTION_URL);
                                } else {
                                    // This path is less common, usually unsubscribe() resolves to true or rejects
                                    console.warn('Browser unsubscription call did not return true.');
                                    throw new Error('Browser unsubscription did not complete as expected.');
                                }
                            });
                    } else {
                        console.log('No active subscription found in browser to unsubscribe.');
                        return Promise.resolve({ status: 'success', message: 'No active subscription found in browser.' }); // Consider this a success for UI update
                    }
                })
                .then(responseJson => {
                    if (responseJson && responseJson.status === 'success') {
                        console.log('Unsubscription processed by server.');
                        // statusMessage will be updated by initializePushUIState
                    } else {
                        console.error('Server failed to process unsubscription:', responseJson);
                        if (statusMessage) statusMessage.textContent = 'Unsubscription attempt partly failed on server.';
                        if (errorMessage) errorMessage.textContent = responseJson ? responseJson.message : 'Unknown server error during unsubscription.';
                    }
                })
                .catch(err => {
                    console.error('Error unsubscribing: ', err);
                    if (statusMessage) statusMessage.textContent = 'Unsubscription failed.';
                    if (errorMessage) errorMessage.textContent = `Error: ${err.message}`;
                })
                .finally(() => {
                    // Always re-check and update UI after attempt
                    initializePushUIState();
                    if (unsubscribeButton) unsubscribeButton.disabled = false;
                });
        });
    } else {
        console.warn('Unsubscribe button (#unsubscribe-button-modal) not found.');
    }

    // Function to send subscription data to your Django backend
    function sendSubscriptionToServer(subscriptionDataPayload, httpMethod, url) {
        // For POST to save_subscription, subscriptionDataPayload is the full PushSubscription object (already toJSON()ed by caller for save)
        // For POST to delete_subscription, subscriptionDataPayload is { endpoint: '...' }
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(subscriptionDataPayload)
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().catch(() => ({ message: `Server error: ${response.status} ${response.statusText}` })).then(errData => {
                        const message = errData.message || `Server error: ${response.status} ${response.statusText}`;
                        console.error('Server responded with an error:', message, 'Status:', response.status);
                        throw new Error(message);
                    });
                }
                return response.json();
            })
            .catch(error => {
                console.error('Error sending subscription data to server:', error);
                if (errorMessage) errorMessage.textContent = `Server communication error: ${error.message}`;
                return Promise.resolve({ status: 'error', message: error.message }); // Ensure promise chain continues
            });
    }
});



