/**
 * The Background Script (Service Worker in Chrome, Event Page in Firefox)
 * Handles the API call to your Python backend to bypass CORS restrictions.
 */

// Use 'browser' for Firefox compatibility, fallback to 'chrome'
const extensionApi = typeof browser !== 'undefined' ? browser : chrome;

extensionApi.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'SAVE_JOB') {
        console.log("Attempting to save job:", message.data.title);

        fetch('http://localhost:8000/add-job', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(message.data)
        })
            .then(async (response) => {
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(errorText || `Server responded with ${response.status}`);
                }
                return response.json();
            })
            .then(result => {
                sendResponse({ success: true, result });
            })
            .catch(error => {
                console.error("Background fetch error:", error);
                sendResponse({ success: false, error: error.message });
            });

        return true; // Keeps the message channel open for async response
    }
});

// Broadcast URL changes to the content script
function handleNavigation(details) {
    if (details.frameId === 0) { // Only top-level frame
        console.log("Navigation detected:", details.url);

        // We need to send this to the specific tab that navigated
        extensionApi.tabs.sendMessage(details.tabId, {
            type: 'URL_CHANGED',
            url: details.url
        }).catch(err => {
            // Ignore errors if content script isn't ready or listening yet
            // This often happens on the very first load before content script injects, 
            // but 'onCompleted' usually catches it.
            // console.debug("Could not send URL_CHANGED:", err);
        });
    }
}

// Listen for History API updates (SPA navigation)
if (extensionApi.webNavigation) {
    const filter = { url: [{ hostContains: 'linkedin.com', pathContains: '/jobs/' }] };

    extensionApi.webNavigation.onHistoryStateUpdated.addListener(handleNavigation, filter);
    extensionApi.webNavigation.onCompleted.addListener(handleNavigation, filter);
} else {
    console.warn("webNavigation permission is missing!");
}