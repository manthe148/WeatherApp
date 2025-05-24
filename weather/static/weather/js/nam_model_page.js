// weather/static/weather/js/weather_models.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("Weather Models JS Initializing (Slider, Local Times, Multi-Param, Preloading)");

    // --- 1. Check for Essential Global Variables from Django Template ---
    if (typeof jsApiUrl === 'undefined' || jsApiUrl === '') {
        console.error("JS FATAL: jsApiUrl is UNDEFINED or EMPTY."); return;
    }
    if (typeof initialFHR === 'undefined') {
        console.error("JS FATAL: initialFHR is UNDEFINED."); return;
    }
    if (typeof initialParamCode === 'undefined') {
        console.error("JS FATAL: initialParamCode is UNDEFINED."); return;
    }

    // --- NEW: Variables for Preloading ---
    if (typeof namRunDateStrGlobal === 'undefined') {
        console.error("JS FATAL: namRunDateStrGlobal is UNDEFINED (for preloading)."); return;
    }
    if (typeof namModelRunHourStrGlobal === 'undefined') {
        console.error("JS FATAL: namModelRunHourStrGlobal is UNDEFINED (for preloading)."); return;
    }
    if (typeof mediaUrlModelPlotsGlobal === 'undefined') {
        console.error("JS FATAL: mediaUrlModelPlotsGlobal is UNDEFINED (for preloading)."); return;
    }

    let availableFHRsList = [];
    try {
        availableFHRsList = JSON.parse(document.getElementById('available_fhrs_data').textContent);
    } catch (e) {
        console.error("JS FATAL: Could not parse available_fhrs_data.", e); return;
    }

    let availableParametersList = [];
    try {
        availableParametersList = JSON.parse(document.getElementById('available_parameters_data').textContent);
    } catch (e) {
        console.error("JS FATAL: Could not parse available_parameters_data.", e); return;
    }

    const initialRunTime = (typeof initialFormattedRunTime !== 'undefined') ? initialFormattedRunTime : "Run time N/A";
    const initialValidTime = (typeof initialFormattedValidTime !== 'undefined') ? initialFormattedValidTime : "Valid time N/A";

    console.log("JS Init Data: API URL =", jsApiUrl, "| Initial FHR =", initialFHR, "| Initial Param =", initialParamCode);
    console.log("JS Init Times: Run =", initialRunTime, "| Valid =", initialValidTime);
    console.log("JS Preload Data: RunDate=", namRunDateStrGlobal, "RunHour=", namModelRunHourStrGlobal, "MediaBase=", mediaUrlModelPlotsGlobal);

    // --- 2. Get DOM Elements ---
    // ... (your existing DOM element fetching) ...
    const imageElement = document.getElementById('model-plot-image');
    const statusMessageElement = document.getElementById('model-status-message');
    const modelRunTimeDisplayElement = document.getElementById('model-run-time-display');
    const modelValidTimeDisplayElement = document.getElementById('model-valid-time-display');
    const modelMainHeadingElement = document.getElementById('model-main-heading');
    const noImageMessageElement = document.getElementById('no-image-message');
    const forecastButtons = document.querySelectorAll('.forecast-hour-btn');
    const paramButtons = document.querySelectorAll('.model-param-btn');
    const fhrSlider = document.getElementById('fhr-slider');
    const fhrSliderValueDisplay = document.getElementById('fhr-slider-value-display');

    if (!imageElement || !statusMessageElement || !modelMainHeadingElement || !noImageMessageElement || !modelRunTimeDisplayElement || !modelValidTimeDisplayElement) {
        console.error("JS FATAL: One or more critical display elements are missing."); return;
    }

    // --- 3. State Variables ---
    let currentSelectedFHR = initialFHR;
    let currentSelectedParamCode = initialParamCode;

    // --- NEW: Preloading Variables ---
    const imagesToPreloadPool = new Set(); // URLs currently being or successfully preloaded
    const preloadedImageObjects = {};    // Stores the Image objects themselves

    // --- NEW: Preloading Functions ---
    function getParameterPrefix(paramCode) {
        const paramInfo = availableParametersList.find(p => p.code === paramCode);
        return paramInfo ? paramInfo.output_file_prefix : null;
    }

    function buildImageUrl(paramPrefix, runDate, runHour, fhr) {
        if (!paramPrefix || !runDate || !runHour || !fhr) return null;
        // NAM FHRs are 2 digits (e.g., 00, 06, 12). GFS is 3 digits. Adjust as needed.
        // This script seems to be for NAM based on context, so padStart(2, '0').
        // If this script is generic, you'll need to pass model type or FHR length.
        const fhrPadding = (jsApiUrl.includes("gfs")) ? 3 : 2; // Simple check, make more robust if needed
        const formattedFHR = fhr.toString().padStart(fhrPadding, '0');
        return `${mediaUrlModelPlotsGlobal}${paramPrefix}_${runDate}_${runHour}z_f${formattedFHR}.png`;
    }

    function actualPreloadImage(url) {
        if (!url || imagesToPreloadPool.has(url)) {
            return; // Already preloaded or in queue
        }
        imagesToPreloadPool.add(url);

        console.log(`Preloading: ${url}`);
        const img = new Image();
        img.src = url;
        preloadedImageObjects[url] = img; // Store the Image object

        img.onload = () => {
            console.log(`Successfully preloaded: ${url}`);
            // Image is in cache. No need to remove from imagesToPreloadPool,
            // as it signifies the browser was instructed to fetch it.
        };
        img.onerror = () => {
            console.error(`Failed to preload: ${url}`);
            imagesToPreloadPool.delete(url); // Allow trying again if it failed
            delete preloadedImageObjects[url];
        };
    }

    function preloadNeighboringImages(targetFHR, targetParamCode, numNeighbors = 2) {
        console.log(`Preloading neighbors for FHR: ${targetFHR}, Param: ${targetParamCode}`);
        const paramPrefix = getParameterPrefix(targetParamCode);
        if (!paramPrefix) {
            console.warn("Cannot preload: No parameter prefix found for", targetParamCode);
            return;
        }

        const currentIndex = availableFHRsList.indexOf(targetFHR);
        if (currentIndex === -1) {
            console.warn("Cannot preload: Current FHR not in available list.");
            return;
        }

        for (let i = 1; i <= numNeighbors; i++) {
            // Preload previous images
            if (currentIndex - i >= 0) {
                const prevFHR = availableFHRsList[currentIndex - i];
                const urlToPreload = buildImageUrl(paramPrefix, namRunDateStrGlobal, namModelRunHourStrGlobal, prevFHR);
                actualPreloadImage(urlToPreload);
            }
            // Preload next images
            if (currentIndex + i < availableFHRsList.length) {
                const nextFHR = availableFHRsList[currentIndex + i];
                const urlToPreload = buildImageUrl(paramPrefix, namRunDateStrGlobal, namModelRunHourStrGlobal, nextFHR);
                actualPreloadImage(urlToPreload);
            }
        }
    }

    // --- 4. UI Update Functions ---
    // ... (your existing updateActiveButtons function, no changes needed here for preloading) ...
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
            // Determine FHR padding based on model (simple check for now)
            const fhrPadding = (jsApiUrl.includes("gfs")) ? 3 : 2;
            fhrSliderValueDisplay.textContent = `F${currentSelectedFHR.padStart(fhrPadding, '0')}`;
        }
        console.log(`UI Active elements updated: Param=${currentSelectedParamCode}, FHR=${currentSelectedFHR}`);
    }


    // ... (your existing updateDisplayInformation function, no changes needed for preloading) ...
    function updateDisplayInformation(data) {
        document.title = data.page_title || "Weather Model"; // Generic title
        if (modelMainHeadingElement) modelMainHeadingElement.textContent = data.main_heading || "Weather Model"; // Use main_heading from API

        if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = data.formatted_run_time_local || "Run: N/A";
        if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = data.formatted_valid_time_local || "Valid: N/A";
        if (statusMessageElement) statusMessageElement.textContent = data.status_message; // This often contains the run/valid times

        if (data.image_exists && data.image_url) {
            // Check if the image is already preloaded and its 'complete' flag is true
            // This is an optimization, browser cache should handle it mostly.
            if (preloadedImageObjects[data.image_url] && preloadedImageObjects[data.image_url].complete) {
                console.log("Using preloaded (and complete) image from cache for display:", data.image_url);
                imageElement.src = data.image_url; // Browser should use cached version
            } else {
                console.log("Setting image src (might be new or not fully preloaded):", data.image_url);
                imageElement.src = data.image_url;
            }
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
        // Don't hide the current image immediately, to reduce flashing if new one loads fast
        // imageElement.style.display = 'none';
        noImageMessageElement.style.display = 'none';

        const urlToFetch = `${jsApiUrl}?fhr=${fhr}&param=${paramCode}`;
        console.log("Constructed URL for fetch:", urlToFetch);

        fetch(urlToFetch)
            .then(response => {
                console.log("Fetch response received. Status:", response.status, response.statusText);
                if (!response.ok) {
                    return response.text().then(text => {
                        throw new Error(`Network error ${response.status}: ${response.statusText}. Server: ${text.substring(0, 200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("API JSON Response:", data);

                // Update state *before* UI updates that depend on this state
                currentSelectedFHR = data.current_fhr;
                currentSelectedParamCode = data.current_param_code;

                updateDisplayInformation(data);
                updateActiveButtons();

                try {
                    history.pushState({ fhr: currentSelectedFHR, param: currentSelectedParamCode }, '', `?param=${currentSelectedParamCode}&fhr=${currentSelectedFHR}`);
                } catch (histError) { console.warn("Could not update browser history:", histError); }

                // --- NEW: Trigger preloading after successful fetch and state update ---
                preloadNeighboringImages(currentSelectedFHR, currentSelectedParamCode);

                // Restore scroll position
                const restoreScroll = () => {
                    console.log("Restoring scroll to:", currentScrollY);
                    window.scrollTo(0, currentScrollY);
                };

                if (data.image_exists && data.image_url) {
                    // If the src is already set to this URL by preloading,
                    // the browser might render it quickly.
                    // If imageElement.src is ALREADY data.image_url, onload might not fire consistently.
                    // So we handle display change first.
                    if (imageElement.src !== data.image_url) {
                        imageElement.onload = () => {
                            console.log("New image fully loaded via src attribute.");
                            restoreScroll();
                            imageElement.onload = null; // Clean up
                            imageElement.onerror = null;
                        };
                        imageElement.onerror = () => {
                            console.error("Failed to load new image src (onerror):", data.image_url);
                            noImageMessageElement.textContent = data.status_message || "Failed to load image.";
                            noImageMessageElement.style.display = 'block';
                            imageElement.style.display = 'none';
                            restoreScroll();
                            imageElement.onload = null; // Clean up
                            imageElement.onerror = null;
                        };
                        imageElement.src = data.image_url; // This triggers the load
                    } else if (imageElement.complete) { // src is same, and image is complete (likely from preload)
                        console.log("Image src is same and complete, restoring scroll.");
                        restoreScroll();
                    } else { // src is same, but not complete (rare, but handle)
                        imageElement.onload = () => {
                            console.log("Image src was same, now loaded, restoring scroll.");
                            restoreScroll();
                            imageElement.onload = null; imageElement.onerror = null;
                        }
                    }
                } else { // No image exists
                    setTimeout(restoreScroll, 0); // Restore scroll after DOM updates
                }
            })
            .catch(error => {
                console.error('Error fetching or processing model plot:', error);
                if (statusMessageElement) statusMessageElement.textContent = `Error: ${error.message}`;
                imageElement.style.display = 'none';
                noImageMessageElement.textContent = `Failed to load model data. ${error.message.substring(0, 150)}`;
                noImageMessageElement.style.display = 'block';
                setTimeout(() => {
                    console.log("Scroll position restored after fetch error to:", currentScrollY);
                    window.scrollTo(0, currentScrollY);
                }, 0);
            });
    }

    // --- 6. Event Listeners ---
    // ... (your existing event listeners for forecastButtons, paramButtons, fhrSlider) ...
    // No changes needed here, as they call fetchModelPlot, which now triggers preloading.
    forecastButtons.forEach(button => {
        button.addEventListener('click', function () {
            fetchModelPlot(this.dataset.fhr, currentSelectedParamCode);
        });
    });

    paramButtons.forEach(button => {
        button.addEventListener('click', function () {
            fetchModelPlot(currentSelectedFHR, this.dataset.paramCode);
        });
    });

    if (fhrSlider) {
        fhrSlider.addEventListener('input', function () {
            const sliderValue = parseInt(this.value, 10);
            // Determine step from slider attributes or default
            let step = 1; // Default step
            if (this.hasAttribute('step')) {
                step = parseInt(this.getAttribute('step'));
                if (isNaN(step) || step <= 0) step = 1; // Fallback for invalid step
            } else { // Infer step for NAM (hourly up to 36, then 3-hourly)
                if (sliderValue > 36) step = 3;
                else step = 1;
            }

            const snappedFhrValue = Math.round(sliderValue / step) * step;
            const fhrPadding = (jsApiUrl.includes("gfs")) ? 3 : 2;
            const formattedFHR = snappedFhrValue.toString().padStart(fhrPadding, '0');


            if (fhrSliderValueDisplay) {
                fhrSliderValueDisplay.textContent = `F${formattedFHR}`;
            }
            // Debounce or fetch on 'change' instead of 'input' if too many requests
            // For now, fetch if FHR actually changes.
            if (currentSelectedFHR !== formattedFHR) {
                fetchModelPlot(formattedFHR, currentSelectedParamCode);
            }
        });
    }


    // --- 7. Initial Page Load Actions ---
    const initialImageRenderedByDjango = imageElement && imageElement.src && imageElement.src.includes(initialParamCode) && imageElement.src.includes(initialFHR) && imageElement.style.display !== 'none';

    console.log("Initial image src from template:", imageElement ? imageElement.src : 'N/A');
    console.log("Initial image considered visible from Django template:", initialImageRenderedByDjango);

    if (initialImageRenderedByDjango) {
        console.log("Initial image already rendered by Django. Setting up UI state and preloading neighbors.");
        if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = initialRunTime;
        if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = initialValidTime;
        updateActiveButtons();
        preloadNeighboringImages(initialFHR, initialParamCode); // <<< INITIAL PRELOAD
    } else if (initialParamCode && initialFHR && jsApiUrl) {
        console.log("No initial image visible from Django, or initial params require JS fetch. Fetching and then preloading.");
        fetchModelPlot(initialFHR, initialParamCode); // Preloading will happen in fetchModelPlot's success
    } else {
        console.warn("Initial param/FHR not fully defined or API URL missing. Skipping initial actions.");
        if (statusMessageElement && imageElement && (!imageElement.src || imageElement.style.display === 'none')) {
            statusMessageElement.textContent = "Select a parameter and forecast hour to load model data.";
            if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = "Run: N/A";
            if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = "Valid: N/A";
        }
        updateActiveButtons();
    }
});