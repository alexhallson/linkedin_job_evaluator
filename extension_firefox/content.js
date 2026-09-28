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
    return {
        title: extractTitle(),
        company: extractCompany(),
        location: extractLocation(),
        link: buildJobLink(),
        description: extractDescription()
    };
}

function extractTitle() {
    // New layout: the job title is the visible text of the link to /jobs/view/{id}.
    const viewLink = document.querySelector('a[href*="/jobs/view/"]');
    if (viewLink) {
        const text = viewLink.textContent.trim();
        if (text && text.length > 2 && text.length < 300) {
            return text;
        }
    }

    // Legacy fallbacks
    const legacy = document.querySelector('.job-details-jobs-unified-top-card__job-title') ||
                   document.querySelector('h1');
    if (legacy) {
        return legacy.textContent.trim();
    }

    return "N/A";
}

function extractCompany() {
    // New layout: LinkedIn exposes an aria-label like "Company, Scale AI."
    const companyWrapper = document.querySelector('[aria-label^="Company, "]');
    if (companyWrapper) {
        const label = companyWrapper.getAttribute('aria-label');
        const match = label.match(/^Company,\s*(.+?)\.?$/);
        if (match && match[1]) {
            return match[1].trim();
        }
    }

    // Fallback: company link text
    const companyLink = document.querySelector('a[href*="/company/"]');
    if (companyLink) {
        const text = companyLink.textContent.trim();
        if (text && text.length > 0 && text.length < 200) {
            return text;
        }
    }

    return "N/A";
}

function extractLocation() {
    // Strategy 1: Location sits in the same metadata paragraph as "Reposted".
    // Find the "Reposted" element and walk backwards to the previous meaningful sibling.
    const repostedEl = Array.from(document.querySelectorAll('span, p, div, li')).find(el =>
        /Reposted/i.test(el.textContent)
    );
    if (repostedEl && repostedEl.parentElement) {
        let sibling = repostedEl.previousElementSibling;
        while (sibling) {
            const text = sibling.textContent?.trim();
            if (text && text.length > 0 && text.length < 200 && !/·/u.test(text)) {
                return text;
            }
            sibling = sibling.previousElementSibling;
        }
    }

    // Strategy 2: scan spans for location-like text.
    const noise = /Reposted|clicked|apply|people|ago|Full-time|Part-time|Contract|Internship|Salary|\$/i;
    for (const span of document.querySelectorAll('span')) {
        const text = span.textContent.trim();
        if (!text || text.length < 2 || text.length > 200) continue;
        if (noise.test(text)) continue;
        // City, State/Country or City, Region, Country
        if (/^[A-Za-z][A-Za-z\s\-]+,\s*[A-Za-z][A-Za-z\s\-]+/.test(text)) {
            return text;
        }
    }

    return "N/A";
}

function extractDescription() {
    // New layout uses a generic expandable text box for the job description.
    const expandable = document.querySelector('[data-testid="expandable-text-box"]');
    if (expandable) {
        return expandable.textContent.trim();
    }

    // Legacy fallbacks
    const legacy = document.querySelector('#job-details') ||
                   document.querySelector('.jobs-description__content') ||
                   document.querySelector('[class*="jobs-description"]');
    if (legacy) {
        return legacy.textContent.trim();
    }

    return "N/A";
}

function buildJobLink() {
    let cleanLink = window.location.href.split('?')[0];
    const urlParams = new URLSearchParams(window.location.search);
    const currentJobId = urlParams.get('currentJobId');

    if (currentJobId) {
        cleanLink = `https://www.linkedin.com/jobs/view/${currentJobId}/`;
    }

    return cleanLink;
}

let lastSavedDescriptionHash = "";
let isPolling = false;
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
    isPolling = false;
}

function startPollingForJob() {
    stopPolling();
    isPolling = true;

    // Safety timeout: stop trying after 10 seconds
    pollingTimeout = setTimeout(() => {
        if (isPolling) {
            console.log("Polling timed out - could not find new stable content.");
            stopPolling();
        }
    }, 10000);

    pollingInterval = setInterval(() => {
        attemptSave();
    }, 100);
}

function attemptSave() {
    const jobData = extractJobData();

    // 1. Wait until all critical fields are loaded
    if (!jobData.description || jobData.description.length < 100) {
        // console.debug("Description too short or missing, waiting...");
        return;
    }

    // Wait until the user has expanded the full description
    if (jobData.description.endsWith('… more')) {
        // console.debug("Description is truncated, waiting for expansion...");
        return;
    }

    if (jobData.title === "N/A" || jobData.company === "N/A") {
        // console.debug("Title or company not yet available, waiting...");
        return;
    }

    // 2. Make sure we are actually on a job page
    if (!jobData.link || !/\/jobs\/view\/\d+/i.test(jobData.link)) {
        // console.debug("Not a recognizable job page URL, skipping.");
        return;
    }

    // 3. Check for Stale Data (Description hasn't changed from previous job)
    const currentHash = simpleHash(jobData.description);
    if (currentHash === lastSavedDescriptionHash) {
        // console.debug("Description matches last saved job. Likely stale DOM. Waiting...");
        return;
    }

    // Found valid, new content!
    stopPolling();
    saveJob(jobData, currentHash);
}

function saveJob(jobData, hash) {
    lastSavedDescriptionHash = hash;
    lastProcessedUrl = jobData.link;

    // Final guard against incomplete data reaching the backend
    if (!jobData.title || jobData.title === "N/A" ||
        !jobData.company || jobData.company === "N/A" ||
        !jobData.description || jobData.description.length < 100) {
        console.warn("Refusing to save job with incomplete data:", jobData);
        toastManager.show(`⚠️ Incomplete job data, skipping.`, 'error');
        return;
    }

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
        startPollingForJob();
    }
});

// Initial run (in case we load on a job page directly)
setTimeout(() => {
    startPollingForJob();
}, 1000);
