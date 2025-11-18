"use strict";

/**
 * Utility function to delay execution
 * @param {Function} func - The function to call after the delay
 * @param {number} delay - The delay in milliseconds
 * @returns {Function} - The debounced function
 */
function debounce(func, delay = 300) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
}

/**
 * Searches for users via the API
 * @param {string} query - The search query
 * @param {string} csrfToken - The CSRF token
 */
async function searchSiteUsers(query, csrfToken) {
    if (query.length < 2) {
        renderSearchResults([]); // Clear results if query is too short
        return;
    }

    try {
        const response = await fetch(`/api/site/search_users?q=${encodeURIComponent(query)}`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });
        if (!response.ok) throw new Error('Search request failed');
        
        const users = await response.json();
        renderSearchResults(users, csrfToken);
    } catch (error) {
        console.error('Error searching users:', error);
    }
}

/**
 * Sends a request to the API to add or remove an admin
 * @param {'add' | 'remove'} action - The action to perform
 * @param {number} accountId - The ID of the account to manage
 * @param {string} csrfToken - The CSRF token
 * @returns {Promise<boolean>} - True if successful, false otherwise
 */
async function manageSiteAdmin(action, accountId, csrfToken) {
    try {
        const body = JSON.stringify({
            action: action,
            account_id: accountId,
        });

        const response = await fetch(`/api/site/manage_admin`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: body
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'API request failed');
        }

        const result = await response.json();
        return result.status === 'ok';
    } catch (error) {
        console.error(`Error ${action}ing admin:`, error);
        return false;
    }
}

/**
 * Renders the search results in the #search-results div
 * @param {Array} users - A list of user objects ({id, nickname, email})
 * @param {string} csrfToken - The CSRF token
 */
function renderSearchResults(users, csrfToken) {
    const resultsContainer = document.getElementById('search-results');
    resultsContainer.innerHTML = ''; // Clear previous results

    if (users.length === 0) {
        return;
    }

    users.forEach(user => {
        const resultItem = document.createElement('div');
        resultItem.className = 'search-result-item'; // Add a class for styling
        resultItem.style.padding = '10px';
        resultItem.style.cursor = 'pointer';
        resultItem.textContent = `${user.nickname} (${user.email})`;
        
        // Store data on the element
        resultItem.dataset.accountId = user.id;
        resultItem.dataset.nickname = user.nickname;
        resultItem.dataset.email = user.email;

        resultItem.onmouseenter = () => resultItem.style.backgroundColor = '#f0f0f0';
        resultItem.onmouseleave = () => resultItem.style.backgroundColor = 'transparent';

        resultItem.addEventListener('click', () => {
            handleAddAdmin(user, csrfToken);
        });
        
        resultsContainer.appendChild(resultItem);
    });
}

/**
 * Handles the click event to add a new admin
 * @param {object} user - The user object ({id, nickname, email})
 * @param {string} csrfToken - The CSRF token
 */
async function handleAddAdmin(user, csrfToken) {
    const success = await manageSiteAdmin('add', user.id, csrfToken);
    
    if (success) {
        // Add to the visual list
        addAdminToList(user);
        
        // Clear search
        document.getElementById('admin-search-bar').value = '';
        document.getElementById('search-results').innerHTML = '';
    } else {
        alert('Failed to add admin. Please try again.');
    }
}

/**
 * Handles the click event to remove an admin
 * @param {Event} event - The click event
 * @param {string} csrfToken - The CSRF token
 */
async function handleRemoveAdmin(event, csrfToken) {
    const button = event.target.closest('[data-action="remove"]');
    if (!button) return;

    const accountId = button.dataset.accountId;
    const listItem = button.closest('li[data-list-item-id]');
    
    if (confirm(`Are you sure you want to remove this admin?`)) {
        const success = await manageSiteAdmin('remove', accountId, csrfToken);
        if (success) {
            removeAdminFromList(listItem);
        } else {
            alert('Failed to remove admin. Please try again.');
        }
    }
}

/**
 * Dynamically adds a new admin to the <ul>
 * @param {object} user - The user object ({id, nickname, email})
 */
function addAdminToList(user) {
    // Remove the "no admins" message if it exists
    const noAdminMessage = document.getElementById('no-admin-message');
    if (noAdminMessage) noAdminMessage.remove();
    
    const list = document.getElementById('current-admin-list');
    const listItem = document.createElement('li');
    listItem.dataset.listItemId = user.id;
    listItem.style.display = 'flex';
    listItem.style.justifyContent = 'space-between';
    listItem.style.width = '100%';
    listItem.style.padding = '5px 0';
    listItem.style.alignItems = 'center';

    // --- SYNTAX FIX: Changed single-quotes to backticks (`) ---
    listItem.innerHTML = `
        <span style="display: flex; align-items: center;">
            ${user.nickname} (${user.email})
        </span>
        <button class="btn-danger" data-action="remove" data-account-id="${user.id}" style="padding: 2px 8px; font-size: 0.9rem; line-height: 1.5;">X</button>
    `;
    // --- END FIX ---

    list.appendChild(listItem);
}

/**
 * Dynamically removes an admin from the <ul>
 * @param {HTMLElement} listItem - The <li> element to remove
 */
function removeAdminFromList(listItem) {
    if (!listItem) return;
    
    listItem.remove();
    
    // Check if list is now empty
    const list = document.getElementById('current-admin-list');
    if (list.children.length === 0) {
        const noAdminMessage = document.createElement('p');
        noAdminMessage.id = 'no-admin-message';
        noAdminMessage.textContent = 'There are no site administrators.';
        list.appendChild(noAdminMessage);
    }
}

/**
 * Initializes all event listeners for the admin management UI
 * @param {string} csrfToken - The CSRF token
 */
function initSiteManagement(csrfToken) {
    const searchBar = document.getElementById('admin-search-bar');
    const adminList = document.getElementById('current-admin-list');

    // Debounced search function
    const debouncedSearch = debounce((query) => {
        searchSiteUsers(query, csrfToken);
    }, 300);

    // Listener for the search bar
    if (searchBar) {
        searchBar.addEventListener('input', (e) => {
            debouncedSearch(e.target.value);
        });
    }

    // Listener for removing admins (using event delegation)
    if (adminList) {
        adminList.addEventListener('click', (e) => {
            handleRemoveAdmin(e, csrfToken);
        });
    }
}