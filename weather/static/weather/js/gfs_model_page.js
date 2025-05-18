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
    const fhrSlider = document.getElementById('fhr-slider'); // Get the slider
    const fhrSliderValueDisplay = document.getElementById('fhr-slider-value'); // Get the span



    let currentSelectedFHR = initialFHR;
    let currentSelectedParamCode = initialParamCode;

    function updateActiveUIElements() {
        // Update Forecast Buttons
        forecastButtons.forEach(btn => {
            const isActive = btn.dataset.fhr === currentSelectedFHR;
            btn.classList.toggle('btn-primary', isActive);
            btn.classList.toggle('active', isActive);
            btn.classList.toggle('btn-outline-primary', !isActive);
        });

        // Update Parameter Buttons (if you have them)
        paramButtons.forEach(btn => {
            const isActive = btn.dataset.paramCode === currentSelectedParamCode;
            btn.classList.toggle('btn-success', isActive);
            btn.classList.toggle('active', isActive);
            btn.classList.toggle('btn-outline-success', !isActive);
        });

        // Update Slider Position and Display Value
        if (fhrSlider && fhrSliderValueDisplay) {
            const numericFHR = parseInt(currentSelectedFHR, 10);
            if (!isNaN(numericFHR)) {
                fhrSlider.value = numericFHR; 
            }
            fhrSliderValueDisplay.textContent = `F${currentSelectedFHR}`;
        }
        console.log(`Active UI updated: Param=<span class="math-inline">\{currentSelectedParamCode\}, FHR\=</span>{currentSelectedFHR}`);
    }
     // --- NEW: Event Listener for the Slider --- 
    
    if (fhrSlider) {
     fhrSlider.addEventListener('input', function() {
        const sliderValue = parseInt(this.value, 10);

        // The HTML <input type="range"> with a 'step' attribute should naturally snap to step values.
        // We just need to format it.
        const formattedFHR = sliderValue.toString().padStart(3, '0');

        // Update the visual display of the slider's current FHR value
        if (fhrSliderValueDisplay) {
            fhrSliderValueDisplay.textContent = `F${formattedFHR}`;
        }

        // Update the globally tracked selected FHR
        currentSelectedFHR = formattedFHR;

        console.log(`Slider 'input' event - FHR: ${currentSelectedFHR}, Param: ${currentSelectedParamCode}. Fetching plot.`);
        fetchModelPlot(currentSelectedFHR, currentSelectedParamCode); 
        // The updateActiveUIElements() call inside fetchModelPlot will handle button highlighting
    });


        // Fetch new plot when slider interaction is done (e.g., on 'change' or 'mouseup')
        fhrSlider.addEventListener('change', function() { // 'change' fires when user releases mouse
            const fhrValue = parseInt(this.value, 10);
            currentSelectedFHR = fhrValue.toString().padStart(3, '0');
            console.log(`Slider changed to FHR: ${currentSelectedFHR}. Param: ${currentSelectedParamCode}`);
            fetchModelPlot(currentSelectedFHR, currentSelectedParamCode);
        });
    }
    // --- END Slider Event Listener ---


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

        const currentScrollY = window.scrollY;

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
            if (!response.ok) { 
                return response.text().then(text => {
                   throw new Error(`Network error ${response.status}: ${response.statusText}. Server detail: ${text.substring(0,200)}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log("API JSON Response:", data);

            document.title = data.page_title || "GFS Model"; 
            if (modelMainHeadingElement) modelMainHeadingElement.textContent = data.page_title || "GFS Model";
            if (statusMessageElement) statusMessageElement.textContent = data.status_message;

            if (data.image_exists && data.image_url && imageElement) {
                // Add an onload handler to the image BEFORE setting the src
                imageElement.onload = function() {
                    console.log("New image loaded. Restoring scroll to:", currentScrollY);
                    window.scrollTo(0, currentScrollY);
                    imageElement.onload = null; // Important to remove the handler to avoid it firing for old images
                    imageElement.onerror = null;
                };
                imageElement.onerror = function() {
                    console.error("Failed to load new image src:", data.image_url);
                    // Still try to restore scroll, then show no-image message
                    window.scrollTo(0, currentScrollY); 
                    if (noImageMessageElement) {
                        noImageMessageElement.textContent = data.status_message || "Failed to load image.";
                        noImageMessageElement.style.display = 'block';
                    }
                    imageElement.style.display = 'none';
                    imageElement.onload = null;
                    imageElement.onerror = null;
                };

                imageElement.src = data.image_url; // Set the new source
                imageElement.alt = data.page_title;
                imageElement.style.display = 'block'; // Make it visible
                if (noImageMessageElement) noImageMessageElement.style.display = 'none';

            } else { // If image_exists is false or no image_url
                if (imageElement) imageElement.style.display = 'none';
                if (noImageMessageElement) {
                    noImageMessageElement.textContent = data.status_message || "Image not available for the selected criteria.";
                    noImageMessageElement.style.display = 'block';
                }
                // Restore scroll position since DOM might have changed
                setTimeout(() => { // Use setTimeout as a fallback if no image load event
                    window.scrollTo(0, currentScrollY);
                    console.log("No image to display, scroll restored to:", currentScrollY);
                }, 0);
            }

            currentSelectedFHR = data.current_fhr; 
            currentSelectedParamCode = data.current_param_code; 
            updateActiveButtons(); 
            try {
                history.pushState({fhr: currentSelectedFHR, param: currentSelectedParamCode}, '', `?param=<span class="math-inline">\{currentSelectedParamCode\}&fhr\=</span>{currentSelectedFHR}`);
            } catch (histError) { 
                console.warn("Could not update browser history:", histError); 
            }
        })
        .catch(error => {
            console.error('Error fetching or processing model plot:', error);
            if (statusMessageElement) statusMessageElement.textContent = `Error: ${error.message}`;
            if (imageElement) imageElement.style.display = 'none';
            if (noImageMessageElement) {
                noImageMessageElement.textContent = `Failed to load model image. ${error.message.substring(0,150)}`;
                noImageMessageElement.style.display = 'block';
            }
            // Optionally restore scroll on error too, if desired
            // setTimeout(() => window.scrollTo(0, currentScrollY), 0);
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

        // --- NEW: Event Listener for the Slider ---
    if (fhrSlider) {
        // Use 'input' event to update AS THE USER DRAGS
        fhrSlider.addEventListener('input', function() {
            const sliderValue = parseInt(this.value, 10);
            // Ensure value aligns with step if browser doesn't enforce perfectly
            const step = parseInt(this.getAttribute('step')) || 6;
            const snappedFhrValue = Math.round(sliderValue / step) * step;

            const formattedFHR = snappedFhrValue.toString().padStart(3, '0');

            if (fhrSliderValueDisplay) {
                fhrSliderValueDisplay.textContent = `F${formattedFHR}`;
            }

            // To avoid too many API calls while dragging, you might want to fetch only on 'change' (on release)
            // OR implement debouncing/throttling here.
            // For now, let's fetch on 'input' as per your request to see the image update.
            if (currentSelectedFHR !== formattedFHR) { // Only fetch if FHR actually changed
                currentSelectedFHR = formattedFHR;
                console.log(`Slider 'input' to FHR: ${currentSelectedFHR}. Param: ${currentSelectedParamCode}.`);
                fetchModelPlot(currentSelectedFHR, currentSelectedParamCode);
            }
        });
    }



    // Initial setup for active buttons and potentially fetching plot if not pre-rendered by Django
    const initialImageElement = document.getElementById('model-plot-image');
    const initialImageIsVisible = initialImageElement && initialImageElement.src && initialImageElement.src !== '' && initialImageElement.style.display !== 'none';
    console.log("Initial image src from template:", initialImageSrc);
    console.log("Initial image truly visible (has src and not display:none):", initialImageIsTrulyVisible);

    if (initialImageIsVisible) {
         updateActiveUIElements(); // This will set initial slider position and button highlights
    } else if (initialParamCode && initialFHR && jsApiUrl) {
         fetchModelPlot(initialFHR, initialParamCode); // This will call updateActiveUIElements on success
    }


});
