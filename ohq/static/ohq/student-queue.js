"use strict"

/*
 * Use a global variable for the socket.  Poor programming style, I know,
 * but I think the simpler implementations of the deleteItem() and addItem()
 * functions will be more approachable for students with less JS experience.
 */
let socket = null
let myAccountID = -1 // Global variable to store the user's account ID


function connectToServer(queueID) {
    // Use wss: protocol if site using https:, otherwise use ws: protocol
    let wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"

    // Create a new WebSocket.
    let url = `${wsProtocol}//${window.location.host}/ohq/data/queue/${queueID}`
    // websocket handshake process done here
    socket = new WebSocket(url)

    // Handle any errors that occur.
    socket.onerror = function(error) {
        displayError("WebSocket Error: " + error) // <-- Fixed: "D" is now "D"
    }

    // Show a connected message when the WebSocket is opened.
    socket.onopen = function(event) {
        displayError("WebSocket Connected")
    }

    // Show a disconnected message when the WebSocket is closed.
    socket.onclose = function(event) {
        displayError("WebSocket Disconnected")
    }

    // Handle messages received from the server.
    socket.onmessage = function(event) {
        let response = JSON.parse(event.data)
        
        // Check for the initial connection message
        if (response.type === 'connection_established') {
            myAccountID = response.my_account_id;
            return; // Don't process this as a state update
        }

        if (response.type === 'announcement') {
            showAnnouncement(response.message);
            return; // Don't process this as a state update
        } else if (response.type === 'queue-deleted') {
            window.location.pathname = ''
            return
        } else if (response.type === 'redirect-home') {
            var message = ''
            if (!response.hasOwnProperty('message')) {
                message = "You do not have permission to access this queue."
            } else {
                message = response.message
            }
            window.location.href = `/?error=${encodeURIComponent(message)}`
            return
        } else if (response.type === 'update-staff-status') {
            isStaff = response['isStaff']
        }
        
        updateState(response)
    }
}

function displayError(message) {
    let errorElement = document.getElementById("error")
    if (errorElement !== null) {
        errorElement.innerHTML = message
    }
}

// ===================SERVER TO CLIENT FUNCTIONS=====================
// This function updates the view in response to server-to-client communication
// Based on what consumers.py tells us, we update what's on the screen
function updateState(response) {
    // For STUDENT VIEW, the ways for state to update in a way that matters (for now):
    // queue is opened or closed
    // you added/removed yourself to the queue or your state on the queue has changed
    if (response.hasOwnProperty('error')) {
        displayError(response.error)
        return
    }

    if (response.hasOwnProperty('queue-status')) {
        updateQueueStatus(response['queue-status'])
    }

    if (response.hasOwnProperty('students')) {
        updateStudents(response['students'])
    }
}

function updateQueueStatus(isOpen) {
    let elem = document.getElementById("queue-status")
    let toggleBtn = document.getElementById("toggle-queue-btn")
    let askBtn = document.getElementById("ask-question-btn")
    
    if (isOpen) {
        elem.innerHTML = "OPEN"
        elem.className = "open-status"
        if (toggleBtn) toggleBtn.innerText = "Close Queue"
        if (askBtn) askBtn.style.visibility = "visible"
    } else {
        elem.innerHTML = "CLOSED"
        elem.className = "close-status"
        if (toggleBtn) toggleBtn.innerText = "Open Queue"
        if (askBtn) askBtn.style.visibility = "hidden"
    }
}

function updateStudents(accountEntryList) {
    // Update total student count
    let countElem = document.getElementById("student-count")
    let verb = accountEntryList.length == 1 ? "is" : "are"
    let students = accountEntryList.length == 1 ? "student" : "students"
    countElem.innerHTML = `${verb} ${accountEntryList.length} ${students}`

    let studentListContainer = document.getElementById("student-queue-list-container")
    studentListContainer.innerHTML = "" // Clear the list
    
    if (accountEntryList.length === 0) {
        studentListContainer.innerHTML = "<p>The queue is empty.</p>"
    }

    // Check if the current user is on the queue
    let userIsOnQueue = false
    let myPosition = -1
    let myEntry = null

    // Render the student list
    accountEntryList.forEach((entry, index) => {
        if (entry.account_id === myAccountID) {
            userIsOnQueue = true
            myPosition = index + 1 // 1-indexed position
            myEntry = entry
        }
        
        if (isStaff) {
            studentListContainer.append(createStaffStudentEntry(entry, index + 1))
        } else {
            studentListContainer.append(createStudentStudentEntry(entry, index + 1))
        }
    })

    // Update student-specific UI (ask box vs. status box)
    if (!isStaff) {
        let askContainer = document.getElementById("ask-question-container")
        let statusContainer = document.getElementById("my-status-container")

        if (userIsOnQueue) {
            // Show status, hide ask box
            askContainer.style.display = "none"
            statusContainer.style.display = "block"
            
            // Update "My Status" card
            document.getElementById("my-position-in-queue").innerText = `#${myPosition}`
            document.getElementById("my-question").innerText = myEntry.question

            // Update status message (e.g., for "frozen")
            let statusMessageElem = document.getElementById("my-status-message")
            let unfreezeBtn = document.getElementById("unfreeze-btn");
            if (myEntry.status === 'frozen') {
                statusMessageElem.innerText = "You have been FROZEN." // Mockup text
                statusMessageElem.style.display = "block"
                unfreezeBtn.style.display = "inline-block";
            } else if (myEntry.status === 'helping') {
                let staffName = myEntry.helping_staff_name || "A TA"
                statusMessageElem.innerText = `${staffName} is coming to help!` // Mockup text
                statusMessageElem.style.display = "block"
                unfreezeBtn.style.display = "none";
            } else {
                statusMessageElem.style.display = "none"
                unfreezeBtn.style.display = "none";
            }

        } else {
            // Show ask box, hide status
            askContainer.style.display = "block"
            statusContainer.style.display = "none"
        }
    }
}

// Creates an HTML element for the staff view of a student
function createStaffStudentEntry(entry, position) {
    let elem = document.createElement("div")
    elem.className = "queue-list-item"

    let statusIndicator = ""
    if (entry.status === 'helping') {
        // Sanitize helping staff name
        let safeStaffName = entry.helping_staff_name ? sanitize(entry.helping_staff_name) : "";
        statusIndicator = `<span class="status-helping">(Helping: ${safeStaffName})</span>`
    } else if (entry.status === 'frozen') {
        statusIndicator = `<span class="status-frozen">(Frozen)</span>`
    }

    // Sanitize name and question
    let safeName = sanitize(entry.name)
    let safeQuestion = sanitize(entry.question)

    let left = `<div><strong>#${position} ${safeName}</strong> ${statusIndicator}<br><p>${safeQuestion}</p></div>`
    
    let buttons = `
        <button class="btn-primary" onclick="helpStudent(${entry.id})">Help</button>
        <button class="btn-secondary" onclick="freezeStudent(${entry.id})">Freeze</button>
        <button class="btn-primary" onclick="finishHelpingStudent(${entry.id})">Finish</button>
    `
    
    elem.innerHTML = `${left}<div>${buttons}</div>`
    return elem
}

// Creates an HTML element for the student view of a student
function createStudentStudentEntry(entry, position) {
    let elem = document.createElement("div")
    elem.className = "queue-list-item"
    
    let myIndicator = (entry.account_id === myAccountID) ? " (You)" : ""
    let statusIndicator = ""
    if (entry.status === 'helping') {
        statusIndicator = `<span class="status-helping">(Being Helped)</span>`
    } else if (entry.status === 'frozen') {
        statusIndicator = `<span class="status-frozen">(Frozen)</span>`
    }
    
    // Sanitize name
    let safeName = sanitize(entry.name)
    
    elem.innerHTML = `<span><strong>#${position} ${safeName}${myIndicator}</strong> ${statusIndicator}</span>`
    return elem
}

// ===================CLIENT TO SERVER FUNCTIONS=====================
// These follow the pattern of constructing a data dictionary
// REQUIRED FIELDS:
// - action (informs consumers.py how to update the model)

// STUDENT ACTIONS
function askQuestion() {
    let questionBox = document.getElementById("question-text-box")
    let questionText = questionBox.value
    if (questionText == "") return
    let data = {action: "ask-question", text: questionText}
    socket.send(JSON.stringify(data))
    questionBox.value = ""
}

function leaveQueue() {
    let data = {action: "leave-queue"}
    socket.send(JSON.stringify(data))
}

function unfreezeMe() {
    let data = {action: "unfreeze"};
    socket.send(JSON.stringify(data));
}

// STAFF ACTIONS
function toggleQueue() {
    let data = {action: "toggle-queue"}
    socket.send(JSON.stringify(data))
}

function freezeStudent(accountEntryId) {
    let data = {action: "freeze", entry_id: accountEntryId}
    socket.send(JSON.stringify(data))
}

function helpStudent(accountEntryId) {
    let data = {action: "help", entry_id: accountEntryId}
    socket.send(JSON.stringify(data))
}

function finishHelpingStudent(accountEntryId) {
    let data = {action: "finish-help", entry_id: accountEntryId}
    socket.send(JSON.stringify(data))
}

function sendAnnouncement() {
    let textBox = document.getElementById("announcement-text-box");
    let text = textBox.value;
    if (text === "") return;
    
    let data = { action: "send-announcement", text: text };
    socket.send(JSON.stringify(data));
    textBox.value = ""; // Clear the box after sending
}


function sendFreezeAll() {
    socket.send(JSON.stringify({ action: "freeze-all" }));
    hideFreezeAllModal();
}



// =================== MODAL FUNCTIONS =====================

function showAnnouncement(message) {
    document.getElementById("announcement-modal-text").innerText = message;
    document.getElementById("announcement-modal-overlay").style.display = "flex";
}

function hideAnnouncement() {
    document.getElementById("announcement-modal-overlay").style.display = "none";
}


function showFreezeAllModal() {
    document.getElementById("freeze-all-modal-overlay").style.display = "flex";
}

function hideFreezeAllModal() {
    document.getElementById("freeze-all-modal-overlay").style.display = "none";
}



// =========================HELPER FUNCTIONS=========================

function sanitize(s) {
    // Be sure to replace ampersand first
    return s.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
}

function getCSRFToken() {
    let cookies = document.cookie.split(";")
    for (let i = 0; i < cookies.length; i++) {
        let c = cookies[i].trim()
        if (c.startsWith("csrftoken=")) {
            return c.substring("csrftoken=".length, c.length)
        }
    }
    return "unknown"
}

// =================== ONLOAD HOOKS =====================

// We need to wait for the DOM to load before adding event listeners
window.addEventListener('load', (event) => {
    // Add listener for the modal close button
    let modalCloseBtn = document.getElementById("announcement-modal-close-btn");
    if (modalCloseBtn) {
        modalCloseBtn.onclick = hideAnnouncement;
    }

    // Add listener for the staff send button (if it exists)
    let sendAnnouncementBtn = document.getElementById("send-announcement-btn");
    if (sendAnnouncementBtn) {
        sendAnnouncementBtn.onclick = sendAnnouncement;
    }

   
    // Add listener for the staff freeze-all button (if it exists)
    let freezeAllBtn = document.getElementById("freeze-all-btn");
    if (freezeAllBtn) {
        freezeAllBtn.onclick = showFreezeAllModal;
    }

    // Add listeners for the new modal's buttons
    let freezeAllConfirmBtn = document.getElementById("freeze-all-confirm-btn");
    if (freezeAllConfirmBtn) {
        freezeAllConfirmBtn.onclick = sendFreezeAll;
    }
    
    let freezeAllCancelBtn = document.getElementById("freeze-all-cancel-btn");
    if (freezeAllCancelBtn) {
        freezeAllCancelBtn.onclick = hideFreezeAllModal;
    }

});