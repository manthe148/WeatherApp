// weather/static/weather/js/weather_models.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("Weather Models JS Initializing (Slider, Local Times, Multi-Param)");

    // --- 1. Check for Essential Global Variables from Django Template ---
    if (typeof jsApiUrl === 'undefined' || jsApiUrl === '') {
        console.error("JS FATAL: jsApiUrl is UNDEFINED or EMPTY. Check inline script in HTML template and the view context variable for 'api_url_for_js'.");
        return;
    }
    if (typeof initialFHR === 'undefined') {
        console.error("JS FATAL: initialFHR is UNDEFINED. Check inline script in HTML template.");
        return;
    }
    if (typeof initialParamCode === 'undefined') {
        console.error("JS FATAL: initialParamCode is UNDEFINED. Check inline script in HTML template.");
        return;
    }
    // Optional initial times (can be "N/A" if image doesn't exist initially)
    const initialRunTime = (typeof initialFormattedRunTime !== 'undefined') ? initialFormattedRunTime : "Run time N/A";
    const initialValidTime = (typeof initialFormattedValidTime !== 'undefined') ? initialFormattedValidTime : "Valid time N/A";

    console.log("JS Init Data: API URL =", jsApiUrl, "| Initial FHR =", initialFHR, "| Initial Param =", initialParamCode);
    console.log("JS Init Times: Run =", initialRunTime, "| Valid =", initialValidTime);

    // --- 2. Get DOM Elements ---
    const imageElement = document.getElementById('model-plot-image');
    const statusMessageElement = document.getElementById('model-status-message'); // For "Loading..." or main status
    const modelRunTimeDisplayElement = document.getElementById('model-run-time-display'); // For local run time
    const modelValidTimeDisplayElement = document.getElementById('model-valid-time-display'); // For local valid time
    const modelMainHeadingElement = document.getElementById('model-main-heading');
    const noImageMessageElement = document.getElementById('no-image-message');

    const forecastButtons = document.querySelectorAll('.forecast-hour-btn');
    const paramButtons = document.querySelectorAll('.model-param-btn');
    const fhrSlider = document.getElementById('fhr-slider');
    const fhrSliderValueDisplay = document.getElementById('fhr-slider-value-display');

    // Check if all critical elements for display exist
    if (!imageElement || !statusMessageElement || !modelMainHeadingElement || !noImageMessageElement || !modelRunTimeDisplayElement || !modelValidTimeDisplayElement) {
        console.error("JS FATAL: One or more critical display elements are missing from the DOM. Check HTML IDs.");
        return;
    }

    // --- 3. State Variables ---
    let currentSelectedFHR = initialFHR;
    let currentSelectedParamCode = initialParamCode;

    // --- 4. UI Update Functions ---
    function updateActiveButtons() {
        forecastButtons.forEach(btn => {
            const isActive = btn.dataset.fhr === currentSelectedFHR;
            btn.classList.toggle('btn-primary', isActive);
            btn.classList.toggle('active', isActive);
            btn.classList.toggle('btn-outline-primary', !isActive);
        });
        paramButtons.forEach(btn => {
            const isActive = btn.dataset.paramCode === currentSelectedParamCode;
            btn.classList.toggle('btn-success', isActive);
            btn.classList.toggle('active', isActive);
            btn.classList.toggle('btn-outline-success', !isActive);
        });
        if (fhrSlider) {
            const numericFHR = parseInt(currentSelectedFHR, 10);
            if (!isNaN(numericFHR) && parseInt(fhrSlider.value, 10) !== numericFHR) {
                fhrSlider.value = numericFHR;
            }
        }
        if (fhrSliderValueDisplay) {
            fhrSliderValueDisplay.textContent = `F${currentSelectedFHR}`;
        }
        console.log(`UI Active elements updated: Param=${currentSelectedParamCode}, FHR=${currentSelectedFHR}`);
    }

    function updateDisplayInformation(data) {
        document.title = data.page_title || "GFS Model";
        if (modelMainHeadingElement) modelMainHeadingElement.textContent = data.page_title || "GFS Model";

        // Update specific time display elements
        if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = data.formatted_run_time_local || "Run: N/A";
        if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = data.formatted_valid_time_local || "Valid: N/A";

        // General status message (might be redundant if specific time elements are used)
        if (statusMessageElement) statusMessageElement.textContent = data.status_message;


        if (data.image_exists && data.image_url) {
            imageElement.src = data.image_url;
            imageElement.alt = data.page_title;
            imageElement.style.display = 'block';
            noImageMessageElement.style.display = 'none';
        } else {
            imageElement.style.display = 'none';
            noImageMessageElement.textContent = data.status_message || "Image not available for the selected criteria.";
            noImageMessageElement.style.display = 'block';
        }
    }

    function fetchModelPlot(fhr, paramCode) {
        console.log(`--- fetchModelPlot called with Param: ${paramCode}, FHR: ${fhr} ---`);
        const currentScrollY = window.scrollY;
        console.log("Storing scrollY:", currentScrollY);

        statusMessageElement.textContent = `Loading F${fhr} for ${paramCode.toUpperCase()} parameter...`;
        imageElement.style.display = 'none';
        noImageMessageElement.style.display = 'none';

        const urlToFetch = `${jsApiUrl}?fhr=${fhr}&param=${paramCode}`;
        console.log("Constructed URL for fetch:", urlToFetch);

        fetch(urlToFetch)
            .then(response => {
                console.log("Fetch response received. Status:", response.status, response.statusText);
                if (!response.ok) {
                    return response.text().then(text => { // Get error text from server
                        throw new Error(`Network error ${response.status}: ${response.statusText}. Server: ${text.substring(0, 200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("API JSON Response:", data);

                currentSelectedFHR = data.current_fhr;
                currentSelectedParamCode = data.current_param_code;

                updateDisplayInformation(data); // Update text, title, heading
                updateActiveButtons();          // Update button/slider active states

                try { // Update browser URL bar
                    history.pushState({ fhr: currentSelectedFHR, param: currentSelectedParamCode }, '', `?param=${currentSelectedParamCode}&fhr=${currentSelectedFHR}`);
                } catch (histError) { console.warn("Could not update browser history:", histError); }

                // Restore scroll position after image potentially loads and reflows
                if (data.image_exists && data.image_url) {
                    imageElement.onload = function () {
                        console.log("New image loaded, restoring scroll to:", currentScrollY);
                        window.scrollTo(0, currentScrollY);
                        imageElement.onload = null;
                        imageElement.onerror = null;
                    };
                    imageElement.onerror = function () {
                        console.error("Failed to load new image src:", data.image_url);
                        window.scrollTo(0, currentScrollY);
                        noImageMessageElement.textContent = data.status_message || "Failed to load image.";
                        noImageMessageElement.style.display = 'block';
                        imageElement.style.display = 'none';
                        imageElement.onload = null;
                        imageElement.onerror = null;
                    };
                    // Setting src here, after onload/onerror are attached
                    imageElement.src = data.image_url;
                } else {
                    // If no image, restore scroll after a brief moment for other DOM changes
                    setTimeout(() => {
                        console.log("No image to display, scroll restored to:", currentScrollY);
                        window.scrollTo(0, currentScrollY);
                    }, 0);
                }
            })
            .catch(error => {
                console.error('Error fetching or processing model plot:', error);
                if (statusMessageElement) statusMessageElement.textContent = `Error: ${error.message}`;
                imageElement.style.display = 'none';
                noImageMessageElement.textContent = `Failed to load model data. ${error.message.substring(0, 150)}`;
                noImageMessageElement.style.display = 'block';
                setTimeout(() => { // Restore scroll on error too
                    console.log("Scroll position restored after fetch error to:", currentScrollY);
                    window.scrollTo(0, currentScrollY);
                }, 0);
            });
    }

    // --- 6. Event Listeners ---
    forecastButtons.forEach(button => {
        button.addEventListener('click', function () {
            // currentSelectedFHR is updated by fetchModelPlot's success handler via API response
            fetchModelPlot(this.dataset.fhr, currentSelectedParamCode);
        });
    });

    paramButtons.forEach(button => {
        button.addEventListener('click', function () {
            // currentSelectedParamCode is updated by fetchModelPlot's success handler via API response
            fetchModelPlot(currentSelectedFHR, this.dataset.paramCode);
        });
    });

    if (fhrSlider) {
        fhrSlider.addEventListener('input', function () {
            const sliderValue = parseInt(this.value, 10);
            const step = parseInt(this.getAttribute('step')) || 6;
            const snappedFhrValue = Math.round(sliderValue / step) * step;
            const formattedFHR = snappedFhrValue.toString().padStart(3, '0');

            if (fhrSliderValueDisplay) {
                fhrSliderValueDisplay.textContent = `F${formattedFHR}`;
            }

            // Only fetch if the actual FHR for the plot would change
            if (currentSelectedFHR !== formattedFHR) {
                // currentSelectedFHR will be updated by fetchModelPlot on success
                fetchModelPlot(formattedFHR, currentSelectedParamCode);
            }
        });
    }

    // --- 7. Initial Page Load Actions ---
    // Check if Django already rendered an image and its details are correct
    const initialImageRenderedByDjango = imageElement && imageElement.src && imageElement.src !== '' && imageElement.style.display !== 'none';

    console.log("Initial image src from template:", imageElement ? imageElement.src : 'N/A');
    console.log("Initial image considered visible from Django template:", initialImageRenderedByDjango);

    if (initialImageRenderedByDjango) {
        console.log("Initial image already rendered by Django. Setting up UI state.");
        // Update the specific time displays with initial values from template
        if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = initialRunTime;
        if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = initialValidTime;
        updateActiveButtons(); // Highlights initial buttons and sets slider value based on initialFHR
    } else if (initialParamCode && initialFHR && jsApiUrl) {
        console.log("No initial image visible from Django, or initial params require JS fetch. Fetching for Param:", initialParamCode, "FHR:", initialFHR);
        fetchModelPlot(initialFHR, initialParamCode); // This will update UI via its success handler
    } else {
        console.warn("Initial param/FHR not fully defined or API URL missing. Skipping initial JS fetch. Check inline script in HTML template.");
        if (statusMessageElement && imageElement && (!imageElement.src || imageElement.style.display === 'none')) {
            statusMessageElement.textContent = "Select a parameter and forecast hour to load model data.";
            if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = "Run: N/A";
            if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = "Valid: N/A";
        }
        updateActiveButtons(); // Still update buttons to default active state
    }
//END OF fetchModelPlot FUNCTION

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