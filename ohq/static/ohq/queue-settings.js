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
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
async function searchUsers(query, queueID, csrfToken, staff=true) {
    if (query.length < 2) {
        renderSearchResults([], queueID, csrfToken, staff); // Clear results if query is too short
        return;
    }

    try {
        const response = await fetch(`/api/queue/${queueID}/search_users?q=${encodeURIComponent(query)}&lookupStaff=${encodeURIComponent(staff)}`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-CSRFToken': csrfToken,
            }
        });
        if (!response.ok) throw new Error('Search request failed');
        
        const users = await response.json();
        renderSearchResults(users, queueID, csrfToken, staff);
    } catch (error) {
        console.error('Error searching users:', error);
    }
}

/**
 * Sends a request to the API to add or remove a staff member
 * @param {'add' | 'remove' | 'toggle_admin'} action - The action to perform
 * @param {number} accountId - The ID of the account to manage
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 * @param {object} payload - Optional extra data to send
 * @returns {Promise<boolean>} - True if successful, false otherwise
 */
async function manageStaff(action, accountId, queueID, csrfToken, payload = {}) {
    try {
        const body = JSON.stringify({
            action: action,
            account_id: accountId,
            ...payload // Spread the payload (e.g., {is_admin: true})
        });

        const response = await fetch(`/api/queue/${queueID}/manage_staff`, {
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
        console.error(`Error ${action}ing staff:`, error);
        return false;
    }
}

/**
 * Renders the search results in the #search-results div
 * @param {Array} users - A list of user objects ({id, nickname, email, isAdmin})
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
function renderSearchResults(users, queueID, csrfToken, staff=true) {
    var resultsContainer
    if (staff) {
        resultsContainer = document.getElementById('search-results');
    } else {
        resultsContainer = document.getElementById('search-results-student')
    }
    resultsContainer.innerHTML = ''; // Clear previous results
    console.log(resultsContainer, staff)

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
        resultItem.dataset.isAdmin = user.isAdmin; // Store isAdmin status

        resultItem.onmouseenter = () => resultItem.style.backgroundColor = '#f0f0f0';
        resultItem.onmouseleave = () => resultItem.style.backgroundColor = 'transparent';

        if (staff) {
            resultItem.addEventListener('click', () => {
                handleAddStaff(user, queueID, csrfToken);
            });
        } else {
            resultItem.addEventListener('click', () => {
                handleAddStudent(user, queueID, csrfToken)
            })
        }
        
        resultsContainer.appendChild(resultItem);
    });
}

/**
 * Handles the click event to add a new staff member
 * @param {object} user - The user object ({id, nickname, email, isAdmin})
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
async function handleAddStaff(user, queueID, csrfToken) {
    const success = await manageStaff('add', user.id, queueID, csrfToken);
    
    if (success) {
        // Add to the visual list
        addStaffToList(user);
        
        // Clear search
        document.getElementById('staff-search-bar').value = '';
        document.getElementById('search-results').innerHTML = '';
    } else {
        alert('Failed to add staff member. Please try again.');
    }
}

/**
 * Handles the click event to remove a staff member
 * @param {Event} event - The click event
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
async function handleRemoveStaff(event, queueID, csrfToken) {
    const button = event.target.closest('[data-action="remove"]');
    if (!button) return;

    const accountId = button.dataset.accountId;
    const listItem = button.closest('li[data-list-item-id]');

    var overlay = document.getElementById('remove-staff-modal-overlay');
    // delete staff button has been clicked. show overlay
    overlay.style.display = 'flex'
    var removeBtn = document.getElementById("remove-staff-confirm-btn")
    if (removeBtn) {
        removeBtn.onclick = async function() {
            const success = await manageStaff('remove', accountId, queueID, csrfToken)
            if (success) {
                removeStaffFromList(listItem)
            } else {
                // show some error
                alert('Failed to remove staff member. Please try again.');
            }
            overlay.style.display = 'none'
        }
    }
}

/**
 * Handles the change event to toggle a staff member's admin status
 * @param {Event} event - The change event
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
async function handleToggleAdmin(event, queueID, csrfToken) {
    const toggle = event.target.closest('.admin-toggle');
    if (!toggle) return; // Event not from an admin toggle

    const accountId = toggle.dataset.accountId;
    const newIsAdminStatus = toggle.checked; // true or false
    
    const payload = { is_admin: newIsAdminStatus };
    const success = await manageStaff('toggle_admin', accountId, queueID, csrfToken, payload);

    if (!success) {
        // Revert the checkbox on failure
        alert('Failed to update admin status.');
        toggle.checked = !newIsAdminStatus;
    }
}


/**
 * Dynamically adds a new staff member to the <ul>
 * @param {object} user - The user object ({id, nickname, email, isAdmin})
 */
function addStaffToList(user) {
    // Remove the "no staff" message if it exists
    const noStaffMessage = document.getElementById('no-staff-message');
    if (noStaffMessage) noStaffMessage.remove();
    
    const list = document.getElementById('current-staff-list');
    const listItem = document.createElement('li');
    listItem.dataset.listItemId = user.id;
    listItem.style.display = 'flex';
    listItem.style.justifyContent = 'space-between';
    listItem.style.width = '100%';
    listItem.style.padding = '5px 0';
    listItem.style.alignItems = 'center';

    const isAdminChecked = user.isAdmin ? 'checked' : '';

    listItem.innerHTML = `
        <span style="display: flex; align-items: center;">
            ${user.nickname} (${user.email})
        </span>
        <button class="btn-danger" data-action="remove" data-account-id="${user.id}" style="padding: 2px 8px; font-size: 0.9rem; line-height: 1.5;">X</button>
    `;
    list.appendChild(listItem);
}

/**
 * Dynamically removes a staff member from the <ul>
 * @param {HTMLElement} listItem - The <li> element to remove
 */
function removeStaffFromList(listItem) {
    if (!listItem) return;
    
    listItem.remove();
    
    // Check if list is now empty
    const list = document.getElementById('current-staff-list');
    if (list.children.length === 0) {
        const noStaffMessage = document.createElement('p');
        noStaffMessage.id = 'no-staff-message';
        noStaffMessage.textContent = 'There are no staff members for this queue.';
        list.appendChild(noStaffMessage);
    }
}

/**
 * Initializes all event listeners for the staff management UI
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
function initStaffManagement(queueID, csrfToken) {
    const searchBar = document.getElementById('staff-search-bar');
    const staffList = document.getElementById('current-staff-list');

    // Debounced search function
    const debouncedSearch = debounce((query) => {
        searchUsers(query, queueID, csrfToken);
    }, 300);

    // Listener for the search bar
    if (searchBar) {
        searchBar.addEventListener('input', (e) => {
            debouncedSearch(e.target.value);
        });
    }

    // Listener for removing staff (using event delegation)
    if (staffList) {
        staffList.addEventListener('click', (e) => {
            handleRemoveStaff(e, queueID, csrfToken);
        });

        staffList.addEventListener('change', (e) => {
            handleToggleAdmin(e, queueID, csrfToken);
        });
    }
}

/**
 * Sends a request to the API to toggle whether the queue is visible
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 * @returns {Promise<boolean>} - True if successful, false otherwise
 */
async function toggleQueueVisibility(queueID, csrfToken, payload = {}) {
    try {
        const body = JSON.stringify({
            ...payload // Spread the payload (e.g., {is_admin: true})
        });

        const response = await fetch(`/api/queue/${queueID}/toggle_queue_visibility`, {
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

        var publicityToggle = document.getElementById("publicity_toggle")
        if (publicityToggle) {
            if (publicityToggle.checked) {
                document.querySelectorAll('.student-management').forEach(elem => elem.style.display = 'none')
                document.getElementById("current-student-list").innerHTML = ""
            } else {
                // private queue
                document.querySelectorAll('.student-management').forEach(elem => elem.style.display = 'block')
                result.students.forEach(staff => addStudentToList(staff))
            }
        }
        return result.status === 'ok';
    } catch (error) {
        console.error(error);
        return false;
    }
}

/**
 * Initializes all event listeners for the staff management UI
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
function initStudentManagement(queueID, csrfToken) {
    const searchBar = document.getElementById('student-search-bar');
    const studentList = document.getElementById('current-student-list');

    // Debounced search function
    const debouncedSearch = debounce((query) => {
        searchUsers(query, queueID, csrfToken, false);
    }, 300);

    // Listener for the search bar
    if (searchBar) {
        searchBar.addEventListener('input', (e) => {
            debouncedSearch(e.target.value);
        });
    }

    // Listener for removing staff (using event delegation)
    if (studentList) {
        studentList.addEventListener('click', (e) => {
            handleRemoveStudent(e, queueID, csrfToken);
        });
    }
}

/**
 * Handles the click event to add a new student
 * @param {object} user - The user object ({id, nickname, email, isAdmin})
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
async function handleAddStudent(user, queueID, csrfToken) {
    const success = await manageStudent('add', user.id, queueID, csrfToken);
    
    if (success) {
        // Add to the visual list
        addStudentToList(user);
        
        // Clear search
        document.getElementById('student-search-bar').value = '';
        document.getElementById('search-results-student').innerHTML = '';
    } else {
        alert('Failed to add student. Please try again.');
    }
}

/**
 * Sends a request to the API to add or remove a student
 * @param {'add' | 'remove' | 'toggle_admin'} action - The action to perform
 * @param {number} accountId - The ID of the account to manage
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 * @param {object} payload - Optional extra data to send
 * @returns {Promise<boolean>} - True if successful, false otherwise
 */
async function manageStudent(action, accountId, queueID, csrfToken, payload = {}) {
    try {
        const body = JSON.stringify({
            action: action,
            account_id: accountId,
            ...payload // Spread the payload (e.g., {is_admin: true})
        });

        const response = await fetch(`/api/queue/${queueID}/manage_student`, {
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
        console.error(`Error ${action}ing student:`, error);
        return false;
    }
}

/**
 * Dynamically adds a new student member to the <ul>
 * @param {object} user - The user object ({id, nickname, email, isAdmin})
 */
function addStudentToList(user) {
    // Remove the "no staff" message if it exists
    const noStudentsMessage = document.getElementById('no-students-message');
    if (noStudentsMessage) noStudentsMessage.remove();
    
    const list = document.getElementById('current-student-list');
    const listItem = document.createElement('li');
    listItem.dataset.listItemId = user.id;
    listItem.style.display = 'flex';
    listItem.style.justifyContent = 'space-between';
    listItem.style.width = '100%';
    listItem.style.padding = '5px 0';
    listItem.style.alignItems = 'center';

    listItem.innerHTML = `
        <span style="display: flex; align-items: center;">
            ${user.nickname} (${user.email})
        </span>
        <button class="btn-danger" data-action="remove" data-account-id="${user.id}" style="padding: 2px 8px; font-size: 0.9rem; line-height: 1.5;">X</button>
    `;
    list.appendChild(listItem);
}

/**
 * Handles the click event to remove a student
 * @param {Event} event - The click event
 * @param {number} queueID - The ID of the current queue
 * @param {string} csrfToken - The CSRF token
 */
async function handleRemoveStudent(event, queueID, csrfToken) {
    const button = event.target.closest('[data-action="remove"]');
    if (!button) return;

    const accountId = button.dataset.accountId;
    const listItem = button.closest('li[data-list-item-id]');

    var overlay = document.getElementById('remove-student-modal-overlay');
    // delete staff button has been clicked. show overlay
    overlay.style.display = 'flex'
    var removeBtn = document.getElementById("remove-student-confirm-btn")
    if (removeBtn) {
        removeBtn.onclick = async function() {
            const success = await manageStudent('remove', accountId, queueID, csrfToken)
            if (success) {
                removeStudentFromList(listItem)
            } else {
                // show some error
                alert('Failed to remove student. Please try again.');
            }
            overlay.style.display = 'none'
        }
    }
}

/**
 * Dynamically removes a student from the <ul>
 * @param {HTMLElement} listItem - The <li> element to remove
 */
function removeStudentFromList(listItem) {
    if (!listItem) return;
    
    listItem.remove();
    
    // Check if list is now empty
    const list = document.getElementById('current-student-list');
    if (list.children.length === 0) {
        const noStudentMessage = document.createElement('p');
        noStudentMessage.id = 'no-students-message';
        noStudentMessage.textContent = 'There are no allowed students for this queue.';
        list.appendChild(noStudentMessage);
    }
}