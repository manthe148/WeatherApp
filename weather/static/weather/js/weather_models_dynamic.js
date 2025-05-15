// weather/static/weather/js/weather_models_dynamic.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("Dynamic Weather Models JS: DOMContentLoaded.");

    // apiUrlModelImageInfo and initialFHR are expected to be global consts from inline script
    if (typeof apiUrlModelImageInfo !== 'undefined') {
        console.log("JS Var: apiUrlModelImageInfo =", apiUrlModelImageInfo);
    } else {
        console.error("JS Var: apiUrlModelImageInfo is UNDEFINED.");
    }
    if (typeof initialFHR !== 'undefined') {
        console.log("JS Var: initialFHR =", initialFHR);
    } else {
        console.error("JS Var: initialFHR is UNDEFINED.");
    }

    const imageElement = document.getElementById('model-plot-image');
    const statusMessageElement = document.getElementById('model-status-message');
//    const pageTitleDisplayElement = document.getElementById('page-title-display');
    const modelMainHeadingElement = document.getElementById('model-main-heading');
    const noImageMessageElement = document.getElementById('no-image-message');
    const forecastButtons = document.querySelectorAll('.forecast-hour-btn');

// --- ADD THESE LOGS TO CHECK ELEMENTS ---
    console.log("Element check - imageElement:", imageElement);
    console.log("Element check - statusMessageElement:", statusMessageElement);
//    console.log("Element check - pageTitleDisplayElement:", pageTitleDisplayElement);
    console.log("Element check - modelMainHeadingElement:", modelMainHeadingElement);
    console.log("Element check - noImageMessageElement:", noImageMessageElement);
    console.log("Element check - forecastButtons found:", forecastButtons.length);
    // --- END ELEMENT CHECK LOGS ---
    console.log('before function');

    function updateActiveButton(selectedFhr) {
        console.log("Updating active button for FHR:", selectedFhr);
        forecastButtons.forEach(btn => {
            if (btn.dataset.fhr === selectedFhr) {
                btn.classList.add('btn-primary', 'active');
                btn.classList.remove('btn-outline-primary');
            } else {
                btn.classList.add('btn-outline-primary');
                btn.classList.remove('btn-primary', 'active');
            }
        });
    };

    function fetchModelPlot(fhr) {
        console.log(`--- fetchModelPlot called with FHR: ${fhr} (type: ${typeof fhr}) ---`); // Log function entry

        // Modify this check to remove pageTitleDisplayElement
        if (!imageElement || !statusMessageElement || !modelMainHeadingElement || !noImageMessageElement) {
            console.error("One or more critical display elements (image, status, heading) are missing from the DOM.");
            return; 
        }

        // --- SUPER DEBUG: Check types and values of variables just before URL construction ---
        console.log("Inside fetchModelPlot - typeof apiUrlModelImageInfo:", typeof apiUrlModelImageInfo);
        console.log("Inside fetchModelPlot - value of apiUrlModelImageInfo:", apiUrlModelImageInfo);
        console.log("Inside fetchModelPlot - typeof fhr:", typeof fhr);
        console.log("Inside fetchModelPlot - value of fhr:", fhr);
    // --- END SUPER DEBUG ---


        if (typeof apiUrlModelImageInfo === 'undefined' || !apiUrlModelImageInfo) {
            console.error("apiUrlModelImageInfo is UNDEFINED or empty inside fetchModelPlot!");
            statusMessageElement.textContent = 'Error: API URL configuration missing.';
            return; // Stop if API URL is missing
        }

        statusMessageElement.textContent = `Loading F${fhr} model data...`;
        imageElement.style.display = 'none';
        noImageMessageElement.style.display = 'none';

        const urlToFetch = apiUrlModelImageInfo + '?fhr=' + fhr;;
        console.log("Constructed URL for fetch:", urlToFetch); // This is the log we're looking for

        fetch(urlToFetch)
            .then(response => {
                console.log("Fetch response received. Status:", response.status);
                if (!response.ok) {
                    console.error("Fetch response not OK. Status Text:", response.statusText);
                    return response.text().then(text => { // Try to get text even on error
                       throw new Error(`Network error: ${response.status} ${response.statusText} - Server said: ${text.substring(0, 200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("API JSON Response:", data);
                // --- CHANGE HOW TITLE IS UPDATED ---
                // if (pageTitleDisplayElement) pageTitleDisplayElement.textContent = data.page_title || "Weather Models"; // REMOVE
                document.title = data.page_title || "Weather Models"; // UPDATE BROWSER TAB TITLE
 
                if (modelMainHeadingElement) modelMainHeadingElement.textContent = data.page_title || "Weather Models";
                statusMessageElement.textContent = data.status_message;

                if (data.image_exists && data.image_url) {
                    imageElement.src = data.image_url;
                    imageElement.alt = data.page_title;
                    imageElement.style.display = 'block';
                    noImageMessageElement.style.display = 'none';
                } else {
                    imageElement.style.display = 'none';
                    noImageMessageElement.textContent = data.status_message || "Image not available for this forecast hour.";
                    noImageMessageElement.style.display = 'block';
                }
                updateActiveButton(data.current_fhr);
                try { // Wrap history.pushState in try-catch as it can fail in some contexts (e.g. file://)
                    history.pushState({fhr: data.current_fhr}, '', `?fhr=${data.current_fhr}`);
                } catch (histError) {
                    console.warn("Could not update browser history:", histError);
                }
            })
            .catch(error => {
                console.error('Error fetching/processing model plot:', error);
                statusMessageElement.textContent = `Error loading data: ${error.message}`;
                noImageMessageElement.textContent = `Error loading data. ${error.message.substring(0,100)}`;
                noImageMessageElement.style.display = 'block';
                imageElement.style.display = 'none';
            });
    }

    forecastButtons.forEach(button => {
        button.addEventListener('click', function () {
            const fhr = this.dataset.fhr;
            console.log(`Forecast hour button F${fhr} clicked.`);
            fetchModelPlot(fhr);
        });
    });

    // Initial load logic
    // Check if initialFHR was defined by the inline script from Django template
    if (typeof initialFHR !== 'undefined' && initialFHR && typeof apiUrlModelImageInfo !== 'undefined' && apiUrlModelImageInfo) {
        console.log("Attempting initial fetch for FHR:", initialFHR);
        // Check if Django already rendered an image
        const initialImageSrc = imageElement ? imageElement.getAttribute('src') : null;
        const initialImageIsTrulyVisible = imageElement && initialImageSrc && initialImageSrc !== '' && imageElement.style.display !== 'none';

        console.log("Initial image src from template:", initialImageSrc);
        console.log("Initial image truly visible:", initialImageIsTrulyVisible);

        if (!initialImageIsTrulyVisible) {
             console.log("No initial image rendered by Django or it's hidden, fetching via JS for FHR:", initialFHR);
             fetchModelPlot(initialFHR);
        } else {
             console.log("Initial image seems to be already rendered by Django. Highlighting button.");
             updateActiveButton(initialFHR);
        }
    } else {
        console.warn("initialFHR or apiUrlModelImageInfo not defined globally from template, or empty. Skipping initial JS fetch.");
        if(statusMessageElement) { // If no image loaded by Django initially
            const initialImageSrc = imageElement ? imageElement.getAttribute('src') : null;
             if (!initialImageSrc || imageElement.style.display === 'none') {
                statusMessageElement.textContent = "Select a forecast hour to load model data.";
             }
        }
    }
});
