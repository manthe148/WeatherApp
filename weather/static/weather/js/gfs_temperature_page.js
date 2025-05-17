// weather/static/weather/js/gfs_temperature_page.js 
// (or weather_models_dynamic.js, whatever your HTML template links to)

document.addEventListener('DOMContentLoaded', function () {
    console.log("Dynamic GFS Page JS Loaded (for multi-parameter).");
    
    // These global consts are expected to be defined by an inline script in your HTML template
    // At the top of DOMContentLoaded:
    if (typeof GFS_API_URL === 'undefined' || !GFS_API_URL) { 
        console.error("JS Var: GFS_API_URL is UNDEFINED or EMPTY. Check HTML template's inline script and view context."); 
        return; 
    }
    console.log("JS Init: GFS_API_URL =", GFS_API_URL);

    // Inside fetchModelPlot:
    if (typeof GFS_API_URL !== 'string' || !GFS_API_URL || /* other checks */ ) { /* error */ }
    const urlToFetch = `<span class="math-inline">\{GFS\_API\_URL\}?fhr\=</span>{fhr}&param=${paramCode}`;

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
    const modelMainHeadingElement = document.getElementById('model-main-heading'); // For the H2 title on the page
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
        console.log(`--- fetchModelPlot called with Param: ${paramCode}, FHR: ${fhr} ---`);
        // --- ADD THESE LOGS ---
        console.log(`Inside fetchModelPlot - Received FHR: '${fhr}', Type: ${typeof fhr}`);
        console.log(`Inside fetchModelPlot - Received ParamCode: '${paramCode}', Type: ${typeof paramCode}`);
        console.log(`Inside fetchModelPlot - Checking API URL variable (e.g., jsApiUrl): '${typeof jsApiUrl !== 'undefined' ? jsApiUrl : "NOT DEFINED OR WRONG NAME"}'`);
        // --- END ADDED LOGS ---


        if (!imageElement || !statusMessageElement || !modelMainHeadingElement || !noImageMessageElement) {
            console.error("JS Error: One or more critical display elements (image, status, heading, no-image message) are missing from the DOM."); 
            return; 
        }
        if (typeof jsApiUrl !== 'string' || !jsApiUrl || 
            typeof fhr !== 'string' || !fhr || 
            typeof paramCode !== 'string' || !paramCode) {
            console.error("JS Error: Missing or invalid API URL, FHR, or ParamCode for fetch call.");
            if(statusMessageElement) statusMessageElement.textContent = 'Error: Internal configuration or parameter selection error.';
            return;
        }

        if(statusMessageElement) statusMessageElement.textContent = `Loading F${fhr} for ${paramCode.toUpperCase()} parameter...`;
        if(imageElement) imageElement.style.display = 'none'; // Hide current image
        if(noImageMessageElement) noImageMessageElement.style.display = 'none'; // Hide no-image message

        const urlToFetch = `${jsApiUrl}?fhr=${fhr}&param=${paramCode}`;
        console.log("Constructed URL for fetch:", urlToFetch);

        fetch(urlToFetch)
            .then(response => {
                console.log("Fetch response received. Status:", response.status);
                if (!response.ok) { 
                    return response.text().then(text => { // Try to get text body from error response
                       throw new Error(`Network error: ${response.status} ${response.statusText} - Server response: ${text.substring(0,200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("API JSON Response:", data);
                document.title = data.page_title || "GFS Model"; // Updates browser tab title
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
                try { // Update browser URL bar
                    history.pushState(
                        {fhr: currentSelectedFHR, param: currentSelectedParamCode}, 
                        '', // title - often ignored by browsers
                        `?param=${currentSelectedParamCode}&fhr=${currentSelectedFHR}` // new URL
                    );
                } catch (histError) { 
                    console.warn("Could not update browser history (pushState not supported or failed):", histError); 
                }
            })
            .catch(error => {
                console.error('Error fetching or processing model plot:', error);
                if (statusMessageElement) statusMessageElement.textContent = `Error: ${error.message}`;
                // Ensure image is hidden and no-image message is shown on error
                if (imageElement) imageElement.style.display = 'none';
                if (noImageMessageElement) {
                    noImageMessageElement.textContent = `Failed to load model image. Please try again or select different options. (${error.message.substring(0,100)})`;
                    noImageMessageElement.style.display = 'block';
                }
            });
    }

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
    
    // Initial setup and potential fetch
    const initialImageElement = document.getElementById('model-plot-image'); // Re-get for safety
    const initialImageSrc = initialImageElement ? initialImageElement.getAttribute('src') : null;
    // Check if image has a src AND is not hidden by style.display = 'none' by Django template
    const initialImageIsTrulyVisible = initialImageElement && initialImageSrc && initialImageSrc !== '' && initialImageElement.style.display !== 'none';

    console.log("Initial image src from template:", initialImageSrc);
    console.log("Initial image truly visible based on src and display style:", initialImageIsTrulyVisible);

    if (initialImageIsTrulyVisible) {
         console.log("Initial image already rendered by Django template. Highlighting active buttons.");
         updateActiveButtons(); 
    } else if (initialParamCode && initialFHR && jsApiUrl) { 
         // If Django didn't provide an image (e.g., image_exists_initial was false), 
         // or if it was hidden, try to fetch it.
         console.log("No initial image visible from Django template, or parameters changed. Fetching via JS for Param:", initialParamCode, "FHR:", initialFHR);
         fetchModelPlot(initialFHR, initialParamCode);
    } else {
        console.warn("Initial param/FHR not fully defined or API URL missing. Skipping initial JS fetch. Check inline script in HTML.");
        if(statusMessageElement && initialImageElement && (!initialImageSrc || initialImageElement.style.display === 'none')) {
             statusMessageElement.textContent = "Select a parameter and forecast hour to load model data.";
        }
    }
});
