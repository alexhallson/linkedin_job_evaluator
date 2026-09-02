/**
 * Content Script for Automatic LinkedIn Job Saving
 * Detects when a job description is visible and automatically sends it to the backend.
 * Uses stacking toasts for notifications.
 */

let lastProcessedUrl = "";

class ToastManager {
    constructor() {
        this.container = document.createElement('div');
        this.container.id = 'job-scraper-toast-container';
        this.container.style = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            align-items: flex-end;
            z-index: 9999;
            pointer-events: none; /* Allow clicks through the container area */
        `;
        document.body.appendChild(this.container);
    }

    show(message, type = 'info', duration = 4000) {
        const toast = document.createElement('div');
        toast.innerText = message;

        // Base Styles
        toast.style = `
            padding: 12px 18px;
            color: white;
            border-radius: 8px;
            font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transition: all 0.3s ease;
            opacity: 0;
            transform: translateX(20px);
            min-width: 200px;
            pointer-events: auto; /* Allow clicking the toast itself if we add close buttons later */
        `;

        // Type Styles
        if (type === 'success') {
            toast.style.backgroundColor = '#057642'; // LinkedIn Green
            toast.style.borderLeft = '4px solid #004d2a';
        } else if (type === 'error') {
            toast.style.backgroundColor = '#dc3545'; // Red
            toast.style.borderLeft = '4px solid #a71d2a';
            duration = 8000; // Errors stay longer
        } else {
            toast.style.backgroundColor = '#333'; // Default/Info
            toast.style.borderLeft = '4px solid #555';
        }

        this.container.appendChild(toast);

        // Animate In
        // Force reflow
        toast.offsetHeight;
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';

        // Auto Dismiss
        setTimeout(() => {
            this.dismiss(toast);
        }, duration);
    }

    dismiss(toast) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        // Remove from DOM after transition
        setTimeout(() => {
            if (toast.parentElement) toast.remove();
        }, 300);
    }
}

const toastManager = new ToastManager();

function extractJobData() {
    let title = "N/A";
    let company = "N/A";
    let location = "N/A";
    let description = "N/A";

    // --- 1. EXTRACT TITLE ---
    // Look for h1, main job links, or legacy top card titles
    const titleEl = document.querySelector('h1') || 
                    document.querySelector('a[href*="/jobs/view/"]') ||
                    document.querySelector('.job-details-jobs-unified-top-card__job-title');
    if (titleEl) {
        title = titleEl.innerText.trim();
    }

    // --- 2. EXTRACT COMPANY ---
    // Find links pointing to company pages or elements with company aria-labels
    const companyEl = document.querySelector('a[href*="/company/"]') ||
                      document.querySelector('[aria-label*="Company"]') ||
                      document.querySelector('.job-details-jobs-unified-top-card__company-name');
    if (companyEl) {
        company = companyEl.innerText.trim();
    }

    // --- 3. EXTRACT LOCATION ---
    // Strategy A: Find text containing location-like patterns near metadata spans
    const metadataSpans = Array.from(document.querySelectorAll('span')).filter(el => {
        const text = el.innerText.trim();
        // Match common location formats (e.g., "London, England, United Kingdom" or "Melbourne, Victoria")
        return text.includes(',') && !text.includes('Reposted') && !text.includes('clicked apply');
    });

    if (metadataSpans.length > 0) {
        location = metadataSpans[0].innerText.trim();
    } else {
        // Strategy B: Legacy fallbacks
        location = document.querySelector('.job-details-jobs-unified-top-card__bullet')?.innerText?.trim() ||
                   document.querySelector('.job-details-jobs-unified-top-card__workplace-type')?.innerText?.trim() ||
                   "N/A";
    }

    // --- 4. EXTRACT DESCRIPTION ---
    const descriptionEl = document.querySelector('#job-details') ||
                          document.querySelector('.jobs-description__content') ||
                          document.querySelector('[class*="description"]');
    if (descriptionEl) {
        description = descriptionEl.innerText.trim();
    }

    // --- 5. URL CONSTRUCTION ---
    let cleanLink = window.location.href.split('?')[0];
    const urlParams = new URLSearchParams(window.location.search);
    const currentJobId = urlParams.get('currentJobId');

    if (currentJobId) {
        cleanLink = `https://www.linkedin.com/jobs/view/${currentJobId}/`;
    }

    return {
        title: title || "N/A",
        company: company || "N/A",
        location: location || "N/A",
        link: cleanLink,
        description: description || "N/A"
    };
}

let lastSavedDescriptionHash = "";
let isPolicing = false;
let pollingInterval;
let pollingTimeout;

function simpleHash(str) {
    let hash = 0;
    if (!str) return hash;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = (hash << 5) - hash + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return hash;
}

function stopPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    if (pollingTimeout) clearTimeout(pollingTimeout);
    isPolicing = false;
}

function startPollingForJob(triggerUrl) {
    stopPolling();
    isPolicing = true;

    // Safety timeout: stop trying after 10 seconds
    pollingTimeout = setTimeout(() => {
        if (isPolicing) {
            console.log("Polling timed out - could not find new stable content.");
            stopPolling();
        }
    }, 10000);

    pollingInterval = setInterval(() => {
        attemptSave(triggerUrl);
    }, 100);
}

function attemptSave(targetUrl) {
    const jobData = extractJobData();

    // 1. Check if description is loaded
    if (!jobData.description || jobData.description.length < 50) {
        // console.debug("Description too short or missing, waiting...");
        return;
    }

    // 2. Check for Stale Data (Description hasn't changed from previous job)
    const currentHash = simpleHash(jobData.description);
    if (currentHash === lastSavedDescriptionHash) {
        // console.debug("Description matches last saved job. Likely stale DOM. Waiting...");
        return;
    }

    // 3. Check for Stale Title (Title mismatch with URL logic if possible, 
    // but mostly relying on description change is safer for now).
    // Sometimes the URL updates before the title in the DOM does.

    // Found valid, new content!
    stopPolling();
    saveJob(jobData, currentHash);
}

function saveJob(jobData, hash) {
    lastSavedDescriptionHash = hash;
    lastProcessedUrl = jobData.link;

    console.log("Auto-saving job:", jobData.title);
    toastManager.show(`Saving ${jobData.title}...`, 'info');

    const api = typeof browser !== 'undefined' ? browser : chrome;

    try {
        api.runtime.sendMessage({ type: 'SAVE_JOB', data: jobData }, (response) => {
            if (api.runtime.lastError) {
                console.error("Runtime error sending message:", api.runtime.lastError);
                toastManager.show(`❌ Ext Error: ${api.runtime.lastError.message}`, 'error');
                return;
            }

            if (response?.success) {
                toastManager.show(`✅ Queued: ${jobData.title}`, 'success');
            } else {
                console.error("Save failed", response);
                toastManager.show(`❌ Failed: ${jobData.title}`, 'error');
            }
        });
    } catch (e) {
        console.error("Exception sending message:", e);
    }
}

// Listen for messages from background script
const api = typeof browser !== 'undefined' ? browser : chrome;
api.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'URL_CHANGED') {
        console.log("URL Changed to:", message.url);
        startPollingForJob(message.url);
    }
});

// Initial run (in case we load on a job page directly)
setTimeout(() => {
    const initialUrl = window.location.href;
    startPollingForJob(initialUrl);
}, 1000);