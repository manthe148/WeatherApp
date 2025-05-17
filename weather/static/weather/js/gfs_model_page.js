// weather/static/weather/js/weather_models.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("Weather Models JS Initializing...");

    // Check if global constants from inline script are defined
    if (typeof jsApiUrl === 'undefined' || jsApiUrl === '') {
        console.error("JS Error: jsApiUrl is UNDEFINED or EMPTY. Check your HTML template's inline script and the view context that provides 'api_url_for_js'.");
        return;
    }
    if (typeof initialFHR === 'undefined') {
        console.error("JS Error: initialFHR is UNDEFINED. Check your HTML template's inline script.");
        return;
    }
    if (typeof initialParamCode === 'undefined') {
        console.error("JS Error: initialParamCode is UNDEFINED. Check your HTML template's inline script.");
        return;
    }

    console.log("JS Init: API URL =", jsApiUrl);
    console.log("JS Init: Initial FHR =", initialFHR);
    console.log("JS Init: Initial Param Code =", initialParamCode);

    const imageElement = document.getElementById('model-plot-image');
    const statusMessageElement = document.getElementById('model-status-message');
    const modelMainHeadingElement = document.getElementById('model-main-heading');
    const noImageMessageElement = document.getElementById('no-image-message');

    const forecastButtons = document.querySelectorAll('.forecast-hour-btn');
    const paramButtons = document.querySelectorAll('.model-param-btn');

    let currentSelectedFHR = initialFHR;
    let currentSelectedParamCode = initialParamCode;

    function updateActiveButtons() {
        forecastButtons.forEach(btn => {
            if (btn.dataset.fhr === currentSelectedFHR) {
                btn.classList.add('btn-primary', 'active');
                btn.classList.remove('btn-outline-primary');
            } else {
                btn.classList.add('btn-outline-primary');
                btn.classList.remove('btn-primary', 'active');
            }
        });
        paramButtons.forEach(btn => {
            if (btn.dataset.paramCode === currentSelectedParamCode) {
                btn.classList.add('btn-success', 'active');
                btn.classList.remove('btn-outline-success');
            } else {
                btn.classList.add('btn-outline-success');
                btn.classList.remove('btn-success', 'active');
            }
        });
        console.log(`Active buttons updated: Param=${currentSelectedParamCode}, FHR=${currentSelectedFHR}`);
    }

    function fetchModelPlot(fhr, paramCode) {
        console.log(`--- fetchModelPlot called with Param: '${paramCode}' (type: ${typeof paramCode}), FHR: '${fhr}' (type: ${typeof fhr}) ---`);

        // Check 1: Critical display elements (keep this)
        if (!imageElement || !statusMessageElement || !modelMainHeadingElement || !noImageMessageElement) {
            console.error("JS Error: One or more critical display elements are missing.");
            return;
        }

        // --- DETAILED DEBUG FOR jsApiUrl BEFORE USE ---
        let currentJsApiUrlValue = "NOT ACCESSIBLE OR WRONG NAME"; // Default error message
        let typeOfJsApiUrl = "N/A";
        try {
            if (typeof jsApiUrl !== 'undefined') { // Check if jsApiUrl is defined in this scope
                currentJsApiUrlValue = jsApiUrl;
                typeOfJsApiUrl = typeof jsApiUrl;
            }
        } catch (e) {
            currentJsApiUrlValue = `Error accessing jsApiUrl: ${e.message}`;
        }
        console.log(`DEBUG URL Build: jsApiUrl value just before use: '${currentJsApiUrlValue}' (type: ${typeOfJsApiUrl})`);
        console.log(`DEBUG URL Build: fhr value just before use: '${fhr}' (type: ${typeof fhr})`);
        console.log(`DEBUG URL Build: paramCode value just before use: '${paramCode}' (type: ${typeof paramCode})`);
        // --- END DETAILED DEBUG ---

        // Check 2: Variable validity (keep this)
        if (typeof jsApiUrl !== 'string' || !jsApiUrl ||
            typeof fhr !== 'string' || !fhr ||
            typeof paramCode !== 'string' || !paramCode) {
            console.error("JS Error: Missing or invalid API URL, FHR, or ParamCode for fetch call based on above values.");
            if (statusMessageElement) statusMessageElement.textContent = 'Error: Internal JS configuration error.';
            return;
        }

        if (statusMessageElement) statusMessageElement.textContent = `Loading F${fhr} for ${paramCode.toUpperCase()}...`;
        if (imageElement) imageElement.style.display = 'none';
        if (noImageMessageElement) noImageMessageElement.style.display = 'none';

        // This is the critical line
        const urlToFetch = `${jsApiUrl}?fhr=${fhr}&param=${paramCode}`;

        console.log("Constructed URL for fetch (final):", urlToFetch);

        fetch(urlToFetch)
            .then(response => {
                console.log("Fetch response received. Status:", response.status);
                if (!response.ok) {
                    // Try to get text from error response to show more details
                    return response.text().then(text => {
                        throw new Error(`Network error ${response.status}: ${response.statusText}. Server detail: ${text.substring(0, 200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("API JSON Response:", data);
                document.title = data.page_title || "GFS Model";
                if (modelMainHeadingElement) modelMainHeadingElement.textContent = data.page_title || "GFS Model";
                if (statusMessageElement) statusMessageElement.textContent = data.status_message;

                if (data.image_exists && data.image_url) {
                    imageElement.src = data.image_url;
                    imageElement.alt = data.page_title;
                    imageElement.style.display = 'block';
                    if (noImageMessageElement) noImageMessageElement.style.display = 'none';
                } else {
                    if (imageElement) imageElement.style.display = 'none';
                    if (noImageMessageElement) {
                        noImageMessageElement.textContent = data.status_message || "Image not available for the selected criteria.";
                        noImageMessageElement.style.display = 'block';
                    }
                }
                currentSelectedFHR = data.current_fhr;
                currentSelectedParamCode = data.current_param_code;
                updateActiveButtons();
                try {
                    // Update browser URL without full reload
                    history.pushState(
                        { fhr: currentSelectedFHR, param: currentSelectedParamCode },
                        '', // title - often ignored
                        // Construct URL relative to current page if base URL is not absolute
                        // For simplicity assuming current page is /weather/models/
                        `?param=${currentSelectedParamCode}&fhr=${currentSelectedFHR}`
                    );
                } catch (histError) {
                    console.warn("Could not update browser history (pushState not supported or failed):", histError);
                }
            })
            .catch(error => {
                console.error('Error fetching or processing model plot:', error);
                if (statusMessageElement) statusMessageElement.textContent = `Error: ${error.message}`;
                if (imageElement) imageElement.style.display = 'none';
                if (noImageMessageElement) {
                    noImageMessageElement.textContent = `Failed to load model image. ${error.message.substring(0, 150)}`;
                    noImageMessageElement.style.display = 'block';
                }
            });
    } // END OF fetchModelPlot FUNCTION

    forecastButtons.forEach(button => {
        button.addEventListener('click', function () {
            currentSelectedFHR = this.dataset.fhr;
            console.log(`Forecast hour button F${currentSelectedFHR} clicked. Current param: ${currentSelectedParamCode}`);
            fetchModelPlot(currentSelectedFHR, currentSelectedParamCode);
        });
    });

    paramButtons.forEach(button => {
        button.addEventListener('click', function () {
            currentSelectedParamCode = this.dataset.paramCode;
            console.log(`Parameter button ${currentSelectedParamCode.toUpperCase()} clicked. Current FHR: ${currentSelectedFHR}`);
            fetchModelPlot(currentSelectedFHR, currentSelectedParamCode);
        });
    });

    // Initial setup for active buttons and potentially fetching plot if not pre-rendered by Django
    const initialImageElement = document.getElementById('model-plot-image');
    const initialImageSrc = initialImageElement ? initialImageElement.getAttribute('src') : null;
    const initialImageIsTrulyVisible = initialImageElement && initialImageSrc && initialImageSrc !== '' && initialImageElement.style.display !== 'none';

    console.log("Initial image src from template:", initialImageSrc);
    console.log("Initial image truly visible (has src and not display:none):", initialImageIsTrulyVisible);

    if (initialImageIsTrulyVisible) {
        console.log("Initial image was rendered by Django template. Highlighting active buttons for Param:", initialParamCode, "FHR:", initialFHR);
        updateActiveButtons();
    } else if (initialParamCode && initialFHR && jsApiUrl) {
        // If Django didn't provide an image (e.g., image_exists_initial was false), fetch it.
        console.log("No initial image visible from Django template, or parameters might have changed from URL. Fetching via JS for Param:", initialParamCode, "FHR:", initialFHR);
        fetchModelPlot(initialFHR, initialParamCode);
    } else {
        console.warn("Initial param/FHR not fully defined or API URL missing. Skipping initial JS fetch or button highlight. Check inline script in HTML template.");
        if (statusMessageElement && initialImageElement && (!initialImageSrc || initialImageElement.style.display === 'none')) {
            statusMessageElement.textContent = "Select a parameter and forecast hour to load model data.";
        }
    }
});