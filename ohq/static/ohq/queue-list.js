"use strict"

/*
 * Use a global variable for the socket.  Poor programming style, I know,
 * but I think the simpler implementations of the deleteItem() and addItem()
 * functions will be more approachable for students with less JS experience.
 */
let socket = null

const maxDescriptionLength = 75

const QueueList = Object.freeze({
    ALL: 'all',
    PINNED: 'pinned',
})


function connectToServer() {
    // Use wss: protocol if site using https:, otherwise use ws: protocol
    let wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"

    // Create a new WebSocket.
    let url = `${wsProtocol}//${window.location.host}/ohq/data/queue-list`
    // websocket handshake process done here
    socket = new WebSocket(url)

    // Handle any errors that occur.
    socket.onerror = function(error) {
        displayError("WebSocket Error: " + error)
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
        updateState(response)
    }

    // Handling updating template upon entering a search query
    let searchInput = document.getElementById("search")
    searchInput.addEventListener('input', searchAction)
}

function displayError(message) {
    let errorElement = document.getElementById("error")
    if (errorElement !== undefined) {
        errorElement.innerHTML = message
    }
}

// ===================SERVER TO CLIENT FUNCTIONS=====================
// This function updates the view in response to server-to-client communication
// Based on what consumers.py tells us, we update what's on the screen
function updateState(response) {
    if (response.hasOwnProperty('error')) {
        displayError(response.error)
        return
    }
    console.log(response)

    // Micro updates to the queue list rather than an action from the user themselves
    if (response.hasOwnProperty('type')) {
        if (response['type'] == 'queue-delete') {
            if (!response.hasOwnProperty('queueID')) {
                displayError("Json missing property 'queueID")
            }
            removeQueueFromPage(response['queueID'])
        }
        return
    }

    // Actions from the user
    if (!response.hasOwnProperty('userID')) {
        displayError("JSON missing property 'userID")
    }
    if (response['userID'] != userID) {
        return
    }
    console.log(response)
    if (response.hasOwnProperty('pinned')) {
        updatePinnedQueueList(response['pinned'])
    }
    // all queues / search results
    if (response.hasOwnProperty('queues')) {
        updateMainQueueList(response['queues'])
    }
}

// Remove queue entry from pinned section and all queues section
function removeQueueFromPage(queueID) {
    let pinnedItems = document.querySelectorAll(".queue-item-box.pinned-list")
    for (let i = 0; i < pinnedItems.length; i++) {
        let element = pinnedItems[i]
        if (element.id == `pinned_queue_${queueID}`) {
            element.remove()
        }
    }
    let queueItems = document.querySelectorAll(".queue-item-box.main-list")
    for (let i = 0; i < queueItems.length; i++) {
        let element = queueItems[i]
        if (element.id == `queue_${queueID}`) {
            element.remove()
        }
    }
}

function updatePinnedQueueList(queueList) {
    let queueItems = document.querySelectorAll(".queue-item-box.pinned-list")
    // remove items that aren't in queueList
    for (let i = 0; i < queueItems.length; i++) {
        let element = queueItems[i]
        let deleteIt = true
        queueList.forEach(item => {
            if (element.id == `pinned_queue_${item.id}`) deleteIt = false
        })
        if (deleteIt) element.remove()
    }

    let list = document.getElementById("pinned-class-grid")
    list.innerHTML = ''
    queueList.forEach(item => {
        list.append(makeQueueItemElement(item, QueueList.PINNED))
    })
}

function updateMainQueueList(queueList) {
    let queueItems = document.querySelectorAll(".queue-item-box.main-list")
    for (let i = 0; i < queueItems.length; i++) {
        let element = queueItems[i]
        element.remove()
    }

    let list = document.getElementById("main-class-grid")
    queueList.forEach(item => {
        if (document.getElementById(`queue_${item.id}`) == null) {
            list.append(makeQueueItemElement(item, QueueList.ALL))
        }
    })
}

// TODO: pin button aesthetics
function makeQueueItemElement(queueItem, queueListType) {
    let className
    let id
    if (queueListType == QueueList.PINNED) {
        className = "pinned-list"
        id = `pinned_queue_${queueItem.id}`
    } else if (queueListType == QueueList.ALL) {
        className = "main-list"
        id = `queue_${queueItem.id}`
    } else if (queueListType == QueueList.SEARCH) {
        className = "search-list"
        id = `search_queue_${queueItem.id}`
    }
    let queueName = `<h2>${queueItem.name}</h2>`

    let descriptionText = queueItem.description.slice(0, maxDescriptionLength)
    // we actually cut off some content
    if (descriptionText.length !== queueItem.description.length) {
        descriptionText = descriptionText.slice(0, -3) + '...'
    }
    let description = `<p>${descriptionText}</p>`
    let openButton = `<a href="/queue/${queueItem.id}" class="btn-primary mt-3">View Queue</a>`

    let pinButton = `<button class="btn-primary" onclick="pinQueue(${queueItem.id})">📌</button>`

    let element = document.createElement("div")
    element.id = id
    element.className = `queue-item-box ${className}`
    if (queueItem.isPublic) {
        element.innerHTML = `<div class="queue-item-box-row">${queueName} ${pinButton}</div>${queueItem.number}<div class="queue-item-box-row">${description} ${openButton}</div>`
    } else {
        // add indication that queue is private
        element.innerHTML = `<div class="queue-item-box-row">${queueName} ${pinButton}</div>${queueItem.number} (Private) <div class="queue-item-box-row">${description} ${openButton}</div>`
    }

    return element
}

// ===================CLIENT TO SERVER FUNCTIONS=====================
// These follow the pattern of constructing a data dictionary
// REQUIRED FIELDS:
// - action (informs consumers.py how to update the model)
// - userID (who are you?)

function pinQueue(queueID) {
    let data = {action: "pin", userID: userID, queueID: queueID}
    socket.send(JSON.stringify(data))
}

function sortQueues(sortType) {
    let data = {action: "sort", userID: userID, type: sortType}
    socket.send(JSON.stringify(data))
}

function searchAction() {
    const searchInput = document.getElementById("search")
    const query = searchInput.value.trim()
    let data = {action: "search", userID: userID, query: query}
    socket.send(JSON.stringify(data))
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