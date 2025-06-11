// weather/static/weather/js/gfs_model_page.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("GFS Models JS Initializing (Slider, Local Times, Multi-Param, Preloading)");

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
    if (typeof gfsRunDateStrGlobal === 'undefined') {
        console.error("JS FATAL: gfsRunDateStrGlobal is UNDEFINED (for preloading)."); return;
    }
    if (typeof gfsModelRunHourStrGlobal === 'undefined') {
        console.error("JS FATAL: gfsModelRunHourStrGlobal is UNDEFINED (for preloading)."); return;
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

    let availableParametersList = []; // Expects list of objects like {code: 't2m', output_file_prefix: 'gfs_t2m_sfc', name: '2m Temp'}
    try {
        availableParametersList = JSON.parse(document.getElementById('available_parameters_data').textContent);
    } catch (e) {
        console.error("JS FATAL: Could not parse available_parameters_data.", e); return;
    }

    const initialRunTime = (typeof initialFormattedRunTime !== 'undefined') ? initialFormattedRunTime : "Run time N/A";
    const initialValidTime = (typeof initialFormattedValidTime !== 'undefined') ? initialFormattedValidTime : "Valid time N/A";

    console.log("JS Init Data: API URL =", jsApiUrl, "| Initial FHR =", initialFHR, "| Initial Param =", initialParamCode);
    console.log("JS Init Times: Run =", initialRunTime, "| Valid =", initialValidTime);
    console.log("JS Preload Data: RunDate=", gfsRunDateStrGlobal, "RunHour=", gfsModelRunHourStrGlobal, "MediaBase=", mediaUrlModelPlotsGlobal);

    // --- 2. Get DOM Elements ---
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
    let currentSelectedFHR = initialFHR; // Should be string e.g. "006"
    let currentSelectedParamCode = initialParamCode;

    // --- NEW: Preloading Variables ---
    const imagesToPreloadPool = new Set();
    const preloadedImageObjects = {};

    // --- NEW: Preloading Functions ---
    function getParameterPrefix(paramCode) {
        const paramInfo = availableParametersList.find(p => p.code === paramCode);
        return paramInfo ? paramInfo.output_file_prefix : null;
    }

    function buildImageUrl(paramPrefix, runDate, runHour, fhr) {
        if (!paramPrefix || !runDate || !runHour || !fhr) return null;
        // GFS FHRs are 3 digits (e.g., 006, 012, 120).
        const formattedFHR = fhr.toString().padStart(3, '0');
        // Example: MEDIA_URL/model_plots/gfs_t2m_sfc_20230501_00z_f006.png
        return `${mediaUrlModelPlotsGlobal}${paramPrefix}_${runDate}_${runHour}z_f${formattedFHR}.png`;
    }

    function actualPreloadImage(url) {
        if (!url || imagesToPreloadPool.has(url)) {
            return;
        }
        imagesToPreloadPool.add(url);
        console.log(`Preloading: ${url}`);
        const img = new Image();
        img.src = url;
        preloadedImageObjects[url] = img;

        img.onload = () => console.log(`Successfully preloaded: ${url}`);
        img.onerror = () => {
            console.error(`Failed to preload: ${url}`);
            imagesToPreloadPool.delete(url);
            delete preloadedImageObjects[url];
        };
    }

    function preloadNeighboringImages(targetFHR, targetParamCode, numNeighbors = 2) {
        console.log(`Preloading neighbors for GFS - FHR: ${targetFHR}, Param: ${targetParamCode}`);
        const paramPrefix = getParameterPrefix(targetParamCode);
        if (!paramPrefix) {
            console.warn("Cannot preload: No parameter prefix found for", targetParamCode);
            return;
        }

        const currentIndex = availableFHRsList.indexOf(targetFHR); // targetFHR must be string from currentSelectedFHR
        if (currentIndex === -1) {
            console.warn("Cannot preload: Current FHR", targetFHR, "not in available list:", availableFHRsList);
            return;
        }

        for (let i = 1; i <= numNeighbors; i++) {
            if (currentIndex - i >= 0) {
                const prevFHR = availableFHRsList[currentIndex - i];
                actualPreloadImage(buildImageUrl(paramPrefix, gfsRunDateStrGlobal, gfsModelRunHourStrGlobal, prevFHR));
            }
            if (currentIndex + i < availableFHRsList.length) {
                const nextFHR = availableFHRsList[currentIndex + i];
                actualPreloadImage(buildImageUrl(paramPrefix, gfsRunDateStrGlobal, gfsModelRunHourStrGlobal, nextFHR));
            }
        }
    }

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
            // currentSelectedFHR is a string like "006". Convert to number for slider value.
            const numericFHR = parseInt(currentSelectedFHR, 10);
            if (!isNaN(numericFHR) && parseInt(fhrSlider.value, 10) !== numericFHR) {
                fhrSlider.value = numericFHR;
            }
        }
        if (fhrSliderValueDisplay) {
            // currentSelectedFHR should already be correctly padded (e.g., "006", "012")
            fhrSliderValueDisplay.textContent = `F${currentSelectedFHR}`;
        }
        console.log(`UI Active elements updated: Param=${currentSelectedParamCode}, FHR=${currentSelectedFHR}`);
    }

    function updateDisplayInformation(data) {
        document.title = data.page_title || "GFS Model";
        if (modelMainHeadingElement) modelMainHeadingElement.textContent = data.page_title || "GFS Model";
        if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = data.formatted_run_time_local || "Run: N/A";
        if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = data.formatted_valid_time_local || "Valid: N/A";
        if (statusMessageElement) statusMessageElement.textContent = data.status_message;

        if (data.image_exists && data.image_url) {
            if (preloadedImageObjects[data.image_url] && preloadedImageObjects[data.image_url].complete) {
                console.log("Using preloaded (and complete) image from cache for display:", data.image_url);
            } else {
                console.log("Setting image src (might be new or not fully preloaded):", data.image_url);
            }
            imageElement.src = data.image_url; // Always set src; browser handles cache.
            imageElement.alt = data.page_title;
            imageElement.style.display = 'block';
            noImageMessageElement.style.display = 'none';
        } else {
            imageElement.style.display = 'none';
            imageElement.src = '';
            noImageMessageElement.textContent = data.status_message || "Image not available for the selected criteria.";
            noImageMessageElement.style.display = 'block';
        }
    }

    // --- 5. Core Logic Function ---
    function fetchModelPlot(fhr, paramCode) {
        console.log(`--- fetchModelPlot called with Param: ${paramCode}, FHR: ${fhr} ---`);
        const currentScrollY = window.scrollY;

        statusMessageElement.textContent = `Loading F${fhr} for ${paramCode.toUpperCase()} parameter...`;
        noImageMessageElement.style.display = 'none';

        const urlToFetch = `${jsApiUrl}?fhr=${fhr}&param=${paramCode}`;
        console.log("Constructed URL for fetch:", urlToFetch);

        fetch(urlToFetch)
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        throw new Error(`Network error ${response.status}: ${response.statusText}. Server: ${text.substring(0, 200)}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("API JSON Response:", data);
                currentSelectedFHR = data.current_fhr; // API provides correctly padded string
                currentSelectedParamCode = data.current_param_code;

                updateDisplayInformation(data);
                updateActiveButtons();

                try {
                    history.pushState({ fhr: currentSelectedFHR, param: currentSelectedParamCode }, '', `?param=${currentSelectedParamCode}&fhr=${currentSelectedFHR}`);
                } catch (histError) { console.warn("Could not update browser history:", histError); }

                // --- Trigger preloading after successful fetch and state update ---
                preloadNeighboringImages(currentSelectedFHR, currentSelectedParamCode);

                const restoreScroll = () => window.scrollTo(0, currentScrollY);

                if (data.image_exists && data.image_url) {
                    if (imageElement.src !== data.image_url || !imageElement.complete) {
                        imageElement.onload = () => {
                            console.log("New image fully loaded via src attribute.");
                            restoreScroll();
                            imageElement.onload = null; imageElement.onerror = null;
                        };
                        imageElement.onerror = () => {
                            console.error("Failed to load new image src (onerror):", data.image_url);
                            noImageMessageElement.textContent = data.status_message || "Failed to load image.";
                            noImageMessageElement.style.display = 'block';
                            imageElement.style.display = 'none';
                            restoreScroll();
                            imageElement.onload = null; imageElement.onerror = null;
                        };
                        // If src isn't already data.image_url, updateDisplayInformation would have set it.
                        // If it was already set (e.g. by preload) and it's not loaded, onload will handle it.
                        // This explicit check handles cases where src might be the same but load failed/didn't complete.
                        if (imageElement.src !== data.image_url) {
                            imageElement.src = data.image_url; // Ensure it's set if updateDisplayInformation didn't already
                        } else if (!imageElement.complete) {
                            // src is same but not complete, Image() might still be loading.
                            // The existing onload/onerror should cover this.
                        } else { // src is same and complete
                            restoreScroll();
                        }

                    } else { // src is same and image is complete
                        restoreScroll();
                    }
                } else {
                    setTimeout(restoreScroll, 0);
                }
            })
            .catch(error => {
                console.error('Error fetching or processing model plot:', error);
                if (statusMessageElement) statusMessageElement.textContent = `Error: ${error.message}`;
                imageElement.style.display = 'none'; imageElement.src = '';
                noImageMessageElement.textContent = `Failed to load model data. ${error.message.substring(0, 150)}`;
                noImageMessageElement.style.display = 'block';
                setTimeout(() => window.scrollTo(0, currentScrollY), 0);
            });
    }

    // --- 6. Event Listeners ---
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
            const step = parseInt(this.getAttribute('step')) || 6; // GFS default step
            const snappedFhrValue = Math.round(sliderValue / step) * step;
            const formattedFHR = snappedFhrValue.toString().padStart(3, '0'); // GFS FHRs are 3 digits

            if (fhrSliderValueDisplay) {
                fhrSliderValueDisplay.textContent = `F${formattedFHR}`;
            }
        });

        fhrSlider.addEventListener('change', function () {
            const sliderValue = parseInt(this.value, 10);
            const step = parseInt(this.getAttribute('step')) || 6;
            const snappedFhrValue = Math.round(sliderValue / step) * step;
            const formattedFHR = snappedFhrValue.toString().padStart(3, '0');

            if (currentSelectedFHR !== formattedFHR) {
                fetchModelPlot(formattedFHR, currentSelectedParamCode);
            }
        });
    }

    // --- 7. Initial Page Load Actions ---
    // More robust check: ensure src actually contains the initial param and fhr if pre-rendered.
    const initialImageSrc = imageElement ? imageElement.getAttribute('src') : '';
    const initialImageRenderedByDjango = initialImageSrc &&
        initialImageSrc.includes(getParameterPrefix(initialParamCode) || ' impossibilemstring') && // Check prefix
        initialImageSrc.includes(`_f${initialFHR}.png`) && // Check FHR
        imageElement.style.display !== 'none';

    console.log("Initial image src from template:", initialImageSrc);
    console.log("Initial image considered valid & visible from Django template:", initialImageRenderedByDjango);

    if (initialImageRenderedByDjango) {
        console.log("Initial image already rendered by Django. Setting up UI state and preloading neighbors.");
        if (modelRunTimeDisplayElement) modelRunTimeDisplayElement.textContent = initialRunTime;
        if (modelValidTimeDisplayElement) modelValidTimeDisplayElement.textContent = initialValidTime;
        updateActiveButtons();
        preloadNeighboringImages(initialFHR, initialParamCode);
    } else if (initialParamCode && initialFHR && jsApiUrl) {
        console.log("No initial image visible/valid from Django, or initial params require JS fetch. Fetching and then preloading.");
        fetchModelPlot(initialFHR, initialParamCode);
    } else {
        console.warn("Initial param/FHR not fully defined or API URL missing. Skipping initial actions.");
        updateActiveButtons();
    }
});