// weather/static/weather/js/weather_models_dynamic.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("Dynamic Weather Models JS Loaded.");

    if (typeof apiUrlModelImageInfo === 'undefined') { console.error("JS Var: apiUrlModelImageInfo is UNDEFINED."); return; }
    if (typeof initialFHR === 'undefined') { console.error("JS Var: initialFHR is UNDEFINED."); return; }
    if (typeof initialParamCode === 'undefined') { console.error("JS Var: initialParamCode is UNDEFINED."); return; }

    console.log("JS Var: apiUrlModelImageInfo =", apiUrlModelImageInfo);
    console.log("JS Var: initialFHR =", initialFHR);
    console.log("JS Var: initialParamCode =", initialParamCode);

    const imageElement = document.getElementById('model-plot-image');
    const statusMessageElement = document.getElementById('model-status-message');
    const modelMainHeadingElement = document.getElementById('model-main-heading');
    const noImageMessageElement = document.getElementById('no-image-message');

    const forecastButtons = document.querySelectorAll('.forecast-hour-btn');
    const paramButtons = document.querySelectorAll('.model-param-btn'); // Get new param buttons

    let currentSelectedFHR = initialFHR;
    let currentSelectedParamCode = initialParamCode; // Store current parameter

    function updateActiveButtons() {
        forecastButtons.forEach(btn => {
            btn.classList.toggle('btn-primary', btn.dataset.fhr === currentSelectedFHR);
            btn.classList.toggle('active', btn.dataset.fhr === currentSelectedFHR);
            btn.classList.toggle('btn-outline-primary', btn.dataset.fhr !== currentSelectedFHR);
        });
        paramButtons.forEach(btn => {
            btn.classList.toggle('btn-success', btn.dataset.paramCode === currentSelectedParamCode);
            btn.classList.toggle('active', btn.dataset.paramCode === currentSelectedParamCode);
            btn.classList.toggle('btn-outline-success', btn.dataset.paramCode !== currentSelectedParamCode);
        });
    }

    function fetchModelPlot(fhr, paramCode) { // Now takes paramCode
        console.log(`--- fetchModelPlot called with Param: ${paramCode}, FHR: ${fhr} ---`);

        if (!imageElement || !statusMessageElement || !modelMainHeadingElement || !noImageMessageElement) {
            console.error("One or more critical display elements are missing from the DOM."); return; 
        }
        if (typeof apiUrlModelImageInfo !== 'string' || !apiUrlModelImageInfo || 
            typeof fhr !== 'string' || !fhr || 
            typeof paramCode !== 'string' || !paramCode) {
            console.error("Missing or invalid API URL, FHR, or ParamCode for fetch.");
            if(statusMessageElement) statusMessageElement.textContent = 'Error: Configuration or parameter selection error.';
            return;
        }

        if(statusMessageElement) statusMessageElement.textContent = `Loading F${fhr} for ${paramCode.toUpperCase()}...`;
        if(imageElement) imageElement.style.display = 'none';
        if(noImageMessageElement) noImageMessageElement.style.display = 'none';

        // Add paramCode to the API URL query
        const urlToFetch = `<span class="math-inline">\{apiUrlModelImageInfo\}?fhr\=</span>{fhr}&param=${paramCode}`;
        console.log("Constructed URL for fetch:", urlToFetch);

        fetch(urlToFetch)
            .then(response => {
                console.log("Fetch response received. Status:", response.status);
                if (!response.ok) { 
                    return response.text().then(text => { 
                       throw new Error(`Network error: ${response.status} ${response.statusText} - Server: ${text.substring(0,200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("API JSON Response:", data);
                document.title = data.page_title || "GFS Model"; // Updates browser tab title
                if (modelMainHeadingElement) modelMainHeadingElement.textContent = data.page_title || "GFS Model";
                if (statusMessageElement) statusMessageElement.textContent = data.status_message;

                if (data.image_exists && data.image_url && imageElement) {
                    imageElement.src = data.image_url;
                    imageElement.alt = data.page_title;
                    imageElement.style.display = 'block';
                    if (noImageMessageElement) noImageMessageElement.style.display = 'none';
                } else {
                    if (imageElement) imageElement.style.display = 'none';
                    if (noImageMessageElement) {
                        noImageMessageElement.textContent = data.status_message || "Image not available.";
                        noImageMessageElement.style.display = 'block';
                    }
                }
                currentSelectedFHR = data.current_fhr; 
                currentSelectedParamCode = data.current_param_code; 
                updateActiveButtons();
                try { // Update browser history to reflect current selection
                    history.pushState({fhr: currentSelectedFHR, param: currentSelectedParamCode}, '', `?param=<span class="math-inline">\{currentSelectedParamCode\}&fhr\=</span>{currentSelectedFHR}`);
                } catch (histError) { console.warn("Could not update browser history:", histError); }
            })
            .catch(error => {
                console.error('Error fetching/processing model plot:', error);
                if (statusMessageElement) statusMessageElement.textContent = `Error: ${error.message}`;
                if (imageElement) imageElement.style.display = 'none';
                if (noImageMessageElement) {
                    noImageMessageElement.textContent = `Failed to load model image. ${error.message.substring(0,100)}`;
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
            fetchModelPlot(currentSelectedFHR, currentSelectedParamCode); // Fetch with new param and current FHR
        });
    });

    const initialImageElement = document.getElementById('model-plot-image');
    const initialImageSrc = initialImageElement ? initialImageElement.getAttribute('src') : null;
    const initialImageIsTrulyVisible = initialImageElement && initialImageSrc && initialImageSrc !== '' && initialImageElement.style.display !== 'none';

    if (!initialImageIsTrulyVisible && initialParamCode && initialFHR) {
         console.log("No initial image by Django or hidden, fetching via JS for Param:", initialParamCode, "FHR:", initialFHR);
         fetchModelPlot(initialFHR, initialParamCode);
    } else if (initialParamCode && initialFHR) { 
         console.log("Initial image rendered by Django. Highlighting buttons for Param:", initialParamCode, "FHR:", initialFHR);
         updateActiveButtons(); 
    } else {
        console.warn("Initial param/FHR not fully defined. Skipping initial JS fetch or button highlight.");
        if(statusMessageElement && initialImageElement && (!initialImageSrc || initialImageElement.style.display === 'none')) {
             statusMessageElement.textContent = "Select a parameter and forecast hour to load model data.";
        }
    }
});
