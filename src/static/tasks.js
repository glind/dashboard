/**
 * Task Management Frontend - JavaScript functionality
 */

// Task Management State
let taskData = {
    tasks: [],
    statistics: {},
    filters: {
        status: 'all',
        priority: 'all', 
        category: 'all',
        includeCompleted: false
    },
    sortBy: 'priority'
};

// Initialize task management
async function initializeTaskManagement() {
    console.log('Initializing Task Management...');
    
    // Load tasks on startup
    await loadTasks();
    
    // Set up event listeners
    setupTaskEventListeners();
    
    // Auto-refresh every 30 seconds
    setInterval(loadTasks, 30000);
}

// Load tasks from API
async function loadTasks() {
    try {
        showTaskLoadingState();
        
        // Build query parameters from current filters
        const params = new URLSearchParams();
        if (taskData.filters.includeCompleted) params.set('include_completed', 'true');
        if (taskData.filters.priority && taskData.filters.priority !== 'all') params.set('priority', taskData.filters.priority);
        if (taskData.filters.status && taskData.filters.status !== 'all') params.set('status', taskData.filters.status);
        if (taskData.filters.category && taskData.filters.category !== 'all') params.set('category', taskData.filters.category);
        
        const response = await fetch(`/api/tasks?${params.toString()}`);
        const data = await response.json();
        
        if (data.success) {
            taskData.tasks = data.tasks || [];
            taskData.statistics = data.statistics || {};
            
            renderTasks();
            renderTaskStatistics();
            
            console.log('Tasks loaded:', taskData.tasks.length);
        } else {
            showTaskError(`Failed to load tasks: ${data.error}`);
        }
        
    } catch (error) {
        console.error('Error loading tasks:', error);
        showTaskError('Failed to load tasks');
    }
}

// Create a new task
async function createTask(taskFormData) {
    try {
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(taskFormData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            await loadTasks(); // Reload tasks
            showTaskSuccess('Task created successfully!');
            return true;
        } else {
            showTaskError(`Failed to create task: ${result.error}`);
            return false;
        }
        
    } catch (error) {
        console.error('Error creating task:', error);
        showTaskError('Failed to create task');
        return false;
    }
}

// Update task status
async function updateTaskStatus(taskId, newStatus) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status: newStatus })
        });
        
        const result = await response.json();
        
        if (result.success) {
            await loadTasks(); // Reload tasks
            showTaskSuccess(`Task marked as ${newStatus}!`);
        } else {
            showTaskError(`Failed to update task: ${result.error}`);
        }
        
    } catch (error) {
        console.error('Error updating task status:', error);
        showTaskError('Failed to update task status');
    }
}

// Delete a task
async function deleteTask(taskId) {
    try {
        if (!confirm('Are you sure you want to delete this task?')) {
            return;
        }
        
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            await loadTasks(); // Reload tasks
            showTaskSuccess('Task deleted successfully!');
        } else {
            showTaskError(`Failed to delete task: ${result.error}`);
        }
        
    } catch (error) {
        console.error('Error deleting task:', error);
        showTaskError('Failed to delete task');
    }
}

// Sync with TickTick
async function syncWithTickTick(direction = 'both') {
    try {
        showTaskInfo('Syncing with TickTick...');
        
        const response = await fetch('/api/tasks/sync', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ direction: direction })
        });
        
        const result = await response.json();
        
        if (result.success) {
            await loadTasks(); // Reload tasks
            
            const syncSummary = [
                `Pushed to TickTick: ${result.tasks_pushed_to_ticktick || 0}`,
                `Pulled from TickTick: ${result.tasks_pulled_from_ticktick || 0}`,
                `Updated: ${result.tasks_updated || 0}`
            ].join(', ');
            
            showTaskSuccess(`TickTick sync completed! ${syncSummary}`);
        } else {
            if (result.error && result.error.includes('not authenticated')) {
                showTaskError('TickTick not authenticated. Please authenticate first.');
            } else {
                showTaskError(`TickTick sync failed: ${result.error}`);
            }
        }
        
    } catch (error) {
        console.error('Error syncing with TickTick:', error);
        showTaskError('Failed to sync with TickTick');
    }
}

// Render tasks in the UI
function renderTasks() {
    const tasksContainer = document.getElementById('tasks-container');
    if (!tasksContainer) return;
    
    // Tasks are already filtered by the API based on our filters
    let filteredTasks = taskData.tasks;
    
    // Sort tasks
    filteredTasks.sort((a, b) => {
        if (taskData.sortBy === 'priority') {
            const priorityOrder = { 'high': 3, 'medium': 2, 'low': 1 };
            return priorityOrder[b.priority] - priorityOrder[a.priority];
        } else if (taskData.sortBy === 'due_date') {
            if (!a.due_date && !b.due_date) return 0;
            if (!a.due_date) return 1;
            if (!b.due_date) return -1;
            return new Date(a.due_date) - new Date(b.due_date);
        } else if (taskData.sortBy === 'created_at') {
            return new Date(b.created_at) - new Date(a.created_at);
        }
        return 0;
    });
    
    if (filteredTasks.length === 0) {
        tasksContainer.innerHTML = `
            <div class="text-center py-8 text-gray-500">
                <p class="text-lg">No tasks found</p>
                <p class="text-sm mt-2">Create a new task or adjust your filters</p>
            </div>
        `;
        return;
    }
    
    const tasksHTML = filteredTasks.map(task => renderTaskCard(task)).join('');
    tasksContainer.innerHTML = tasksHTML;
}

// Render individual task card
function renderTaskCard(task) {
    const priorityColors = {
        'high': 'bg-red-100 border-red-300 text-red-800',
        'medium': 'bg-yellow-100 border-yellow-300 text-yellow-800',
        'low': 'bg-green-100 border-green-300 text-green-800'
    };
    
    const statusColors = {
        'pending': 'bg-blue-100 text-blue-800',
        'in_progress': 'bg-purple-100 text-purple-800',
        'completed': 'bg-green-100 text-green-800',
        'cancelled': 'bg-gray-100 text-gray-800'
    };
    
    const dueDateText = task.due_date ? 
        formatRelativeDate(task.due_date) : 
        '<span class="text-gray-400">No due date</span>';
    
    const emailLink = task.gmail_link ? 
        `<a href="${task.gmail_link}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">📧 View Email</a>` : 
        '';
    
    return `
        <div class="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
            <div class="flex justify-between items-start mb-2">
                <h3 class="font-semibold text-gray-900 flex-grow pr-4">${escapeHtml(task.title)}</h3>
                <div class="flex gap-2 flex-shrink-0">
                    <span class="px-2 py-1 text-xs font-medium rounded-full ${priorityColors[task.priority] || priorityColors.medium}">
                        ${task.priority.toUpperCase()}
                    </span>
                    <span class="px-2 py-1 text-xs font-medium rounded-full ${statusColors[task.status] || statusColors.pending}">
                        ${task.status.replace('_', ' ').toUpperCase()}
                    </span>
                </div>
            </div>
            
            ${task.description ? `<p class="text-gray-600 text-sm mb-3">${escapeHtml(task.description)}</p>` : ''}
            
            <div class="flex justify-between items-center text-sm text-gray-500 mb-3">
                <div class="flex items-center gap-4">
                    <span>📅 ${dueDateText}</span>
                    <span>📂 ${task.category}</span>
                    <span>🔗 ${task.source}</span>
                </div>
                ${emailLink}
            </div>
            
            <div class="flex justify-between items-center">
                <div class="text-xs text-gray-400">
                    Created: ${formatRelativeDate(task.created_at)}
                    ${task.completed_at ? ` • Completed: ${formatRelativeDate(task.completed_at)}` : ''}
                </div>
                
                <div class="flex gap-2">
                    ${task.status === 'pending' ? `
                        <button onclick="updateTaskStatus('${task.id}', 'in_progress')" 
                                class="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded hover:bg-purple-200">
                            Start
                        </button>
                        <button onclick="updateTaskStatus('${task.id}', 'completed')" 
                                class="text-xs bg-green-100 text-green-700 px-2 py-1 rounded hover:bg-green-200">
                            Complete
                        </button>
                    ` : ''}
                    
                    ${task.status === 'in_progress' ? `
                        <button onclick="updateTaskStatus('${task.id}', 'completed')" 
                                class="text-xs bg-green-100 text-green-700 px-2 py-1 rounded hover:bg-green-200">
                            Complete
                        </button>
                        <button onclick="updateTaskStatus('${task.id}', 'pending')" 
                                class="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded hover:bg-gray-200">
                            Pause
                        </button>
                    ` : ''}
                    
                    ${task.status === 'completed' ? `
                        <button onclick="updateTaskStatus('${task.id}', 'pending')" 
                                class="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200">
                            Reopen
                        </button>
                    ` : ''}
                    
                    <button onclick="deleteTask('${task.id}')" 
                            class="text-xs bg-red-100 text-red-700 px-2 py-1 rounded hover:bg-red-200">
                        Delete
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Render task statistics
function renderTaskStatistics() {
    const statsContainer = document.getElementById('task-stats');
    if (!statsContainer) return;
    
    const stats = taskData.statistics;
    
    statsContainer.innerHTML = `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-white p-4 rounded-lg border">
                <div class="text-2xl font-bold text-blue-600">${stats.pending_tasks || 0}</div>
                <div class="text-sm text-gray-600">Pending</div>
            </div>
            <div class="bg-white p-4 rounded-lg border">
                <div class="text-2xl font-bold text-green-600">${stats.completed_tasks || 0}</div>
                <div class="text-sm text-gray-600">Completed</div>
            </div>
            <div class="bg-white p-4 rounded-lg border">
                <div class="text-2xl font-bold text-red-600">${stats.high_priority || 0}</div>
                <div class="text-sm text-gray-600">High Priority</div>
            </div>
            <div class="bg-white p-4 rounded-lg border">
                <div class="text-2xl font-bold text-orange-600">${stats.overdue_tasks || 0}</div>
                <div class="text-sm text-gray-600">Overdue</div>
            </div>
        </div>
        
        ${stats.due_today > 0 ? `
            <div class="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p class="text-yellow-800"><strong>${stats.due_today}</strong> task(s) due today!</p>
            </div>
        ` : ''}
        
        ${stats.due_this_week > 0 ? `
            <div class="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p class="text-blue-800"><strong>${stats.due_this_week}</strong> task(s) due this week</p>
            </div>
        ` : ''}
    `;
}

// Set up event listeners
function setupTaskEventListeners() {
    // Task filter buttons
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('task-filter-btn')) {
            const filterType = e.target.dataset.filterType || 'status';
            const filterValue = e.target.dataset.filter;
            
            // Update filter state
            taskData.filters[filterType] = filterValue;
            
            // Update active button in this filter group
            const filterGroup = e.target.closest('.filter-group');
            if (filterGroup) {
                filterGroup.querySelectorAll('.task-filter-btn').forEach(btn => {
                    btn.classList.remove('bg-blue-600', 'text-white');
                    btn.classList.add('bg-gray-200', 'text-gray-700');
                });
                e.target.classList.remove('bg-gray-200', 'text-gray-700');
                e.target.classList.add('bg-blue-600', 'text-white');
            }
            
            // Reload tasks with new filters
            loadTasks();
        }
    });
    
    // Sort dropdown
    const sortSelect = document.getElementById('task-sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            taskData.sortBy = e.target.value;
            renderTasks();
        });
    }
    
    // New task form
    const newTaskForm = document.getElementById('new-task-form');
    if (newTaskForm) {
        newTaskForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const taskData = {
                title: formData.get('title'),
                description: formData.get('description'),
                priority: formData.get('priority'),
                category: formData.get('category'),
                due_date: formData.get('due_date') || null,
                sync_to_ticktick: formData.get('sync_to_ticktick') === 'on'
            };
            
            const success = await createTask(taskData);
            if (success) {
                e.target.reset(); // Clear form
            }
        });
    }
    
    // TickTick sync buttons
    const syncToTickTickBtn = document.getElementById('sync-to-ticktick-btn');
    if (syncToTickTickBtn) {
        syncToTickTickBtn.addEventListener('click', () => syncWithTickTick('to_ticktick'));
    }
    
    const syncFromTickTickBtn = document.getElementById('sync-from-ticktick-btn');
    if (syncFromTickTickBtn) {
        syncFromTickTickBtn.addEventListener('click', () => syncWithTickTick('from_ticktick'));
    }
    
    const syncBothBtn = document.getElementById('sync-both-btn');
    if (syncBothBtn) {
        syncBothBtn.addEventListener('click', () => syncWithTickTick('both'));
    }
    
    // Include completed tasks checkbox
    const includeCompletedCheckbox = document.getElementById('include-completed-tasks');
    if (includeCompletedCheckbox) {
        includeCompletedCheckbox.addEventListener('change', (e) => {
            taskData.filters.includeCompleted = e.target.checked;
            loadTasks();
        });
    }
}

// Utility functions
function formatRelativeDate(dateString) {
    if (!dateString) return 'Unknown';
    
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays === -1) {
            return 'Tomorrow';
        } else if (diffDays > 0) {
            return `${diffDays} days ago`;
        } else {
            return `In ${Math.abs(diffDays)} days`;
        }
    } catch (e) {
        return dateString;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showTaskLoadingState() {
    const container = document.getElementById('tasks-container');
    if (container) {
        container.innerHTML = `
            <div class="text-center py-8">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                <p class="text-gray-600 mt-4">Loading tasks...</p>
            </div>
        `;
    }
}

function showTaskError(message) {
    console.error('Task error:', message);
    showNotification(message, 'error');
}

function showTaskSuccess(message) {
    console.log('Task success:', message);
    showNotification(message, 'success');
}

function showTaskInfo(message) {
    console.log('Task info:', message);
    showNotification(message, 'info');
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 transition-all duration-300 ${
        type === 'error' ? 'bg-red-100 border border-red-300 text-red-800' :
        type === 'success' ? 'bg-green-100 border border-green-300 text-green-800' :
        'bg-blue-100 border border-blue-300 text-blue-800'
    }`;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Export functions for global use
window.taskManagement = {
    initializeTaskManagement,
    loadTasks,
    createTask,
    updateTaskStatus,
    deleteTask,
    syncWithTickTick
};

// Auto-initialize if DOM is already loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTaskManagement);
} else {
    initializeTaskManagement();
}