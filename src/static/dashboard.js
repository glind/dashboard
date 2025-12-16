/**
 * Modern Dashboard Data Loader
 * Handles loading data for all dashboard sections
 */

class DashboardDataLoader {
    constructor() {
        this.todos = [];
        this.calendar = [];
        this.emails = [];
        this.github = {};
        this.news = [];
        this.weather = {};
        this.dashboards = {}; // Marketing dashboards (projects & websites)
        this.aiSuggestions = [];
        this.aiMessages = [];
        this.vanityAlerts = [];
        this.musicNews = [];
        this.upcomingEventTimer = null;
        this.voiceRecognition = null;
        this.speechSynthesis = window.speechSynthesis;
        this.alertedEvents = new Set();
        this.feedbackData = {}; // Store feedback for AI training
        this.dismissedSuggestions = new Set(); // Track dismissed AI suggestions
        this.aiVoiceEnabled = localStorage.getItem('aiVoiceEnabled') !== 'false'; // AI voice responses - persisted
        this.globalMuted = localStorage.getItem('globalMuted') === 'true'; // Global mute for ALL voice alerts
        this.editMode = false;
        this.autoRefreshInterval = 5; // minutes
        this.autoRefreshTimer = null;
        this.backgroundImages = []; // Available background images
        this.currentBackgroundIndex = 0;
        this.backgroundRotation = 'random'; // 'random', 'sequential', 'fixed'
        this.fullPageBackground = false; // Full-page background with transparent cards
        this.savedBackgrounds = []; // Liked backgrounds saved as base64
        this.taskSyncEnabled = false; // TickTick/Todoist sync
        this.taskSyncService = 'ticktick'; // 'ticktick' or 'todoist'
        this.selectedVoice = null; // Selected TTS voice
        this.availableVoices = []; // Available TTS voices
        this.conversationId = null; // Current AI conversation ID
        this.userProfile = null; // User profile for AI
        this.overviewSummary = null; // 5-minute overview summary for AI Assistant
        this.personalizedSuggestion = null; // Random personalized suggestion
        this.showReadArticles = false; // Show read articles in news section
        this.dashboardConfig = {
            overview: true,
            leads: true,
            dashboards: true,
            todos: true,
            calendar: true,
            emails: true,
            github: true,
            news: true,
            weather: true,
            vanity: true,
            liked: true,
            music: true,
            ai: true
        };
        this.initVoiceRecognition();
        this.loadDashboardConfig();
        this.loadAutoRefreshSettings();
        this.loadBackgroundSettings();
        this.loadTaskSyncSettings();
        this.loadVoiceSettings();
        this.loadUserProfile();
        this.updateGlobalMuteButton();
    }
    
    updateGlobalMuteButton() {
        // Update button state on init
        const iconEl = document.getElementById('mute-icon');
        const textEl = document.getElementById('mute-text');
        const btnEl = document.getElementById('global-mute-btn');
        
        if (iconEl && textEl && btnEl) {
            if (this.globalMuted) {
                iconEl.textContent = '🔇';
                textEl.textContent = 'Voice Alerts Off';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            } else {
                iconEl.textContent = '🔊';
                textEl.textContent = 'Voice Alerts On';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            }
        }
    }
    
    initVoiceRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.voiceRecognition = new SpeechRecognition();
            this.voiceRecognition.continuous = false;
            this.voiceRecognition.interimResults = false;
            this.voiceRecognition.lang = 'en-US';
            
            // Create a separate continuous listener for stop commands
            this.stopCommandListener = new SpeechRecognition();
            this.stopCommandListener.continuous = true;
            this.stopCommandListener.interimResults = true;
            this.stopCommandListener.lang = 'en-US';
            
            this.stopCommandListener.onresult = (event) => {
                const transcript = event.results[event.results.length - 1][0].transcript.toLowerCase();
                if (transcript.includes('stop') || transcript.includes('shut up') || transcript.includes('be quiet')) {
                    this.stopSpeech();
                }
            };
            
            this.stopCommandListener.onerror = (event) => {
                if (event.error !== 'no-speech') {
                    console.log('Stop command listener error:', event.error);
                }
            };
            
            this.stopCommandListener.onend = () => {
                // Restart the listener if speech is active
                if (this.speechSynthesis && this.speechSynthesis.speaking) {
                    try {
                        this.stopCommandListener.start();
                    } catch (e) {
                        // Ignore if already started
                    }
                }
            };
        }
    }
    
    startStopCommandListener() {
        if (this.stopCommandListener) {
            try {
                this.stopCommandListener.start();
            } catch (e) {
                // Ignore if already started
            }
        }
    }
    
    stopStopCommandListener() {
        if (this.stopCommandListener) {
            try {
                this.stopCommandListener.stop();
            } catch (e) {
                // Ignore errors
            }
        }
    }
    
    async init() {
        this.loadFeedbackFromStorage();
        this.loadDismissedSuggestions();
        this.loadBackgroundSettings(); // Load and apply background images
        this.checkOAuthCallbackStatus(); // Check for OAuth redirects
        await this.loadAllData();
        await this.loadNewJoke(); // Load initial joke
    }
    
    checkOAuthCallbackStatus() {
        // Check URL params for OAuth callback status
        const params = new URLSearchParams(window.location.search);
        
        if (params.has('spotify')) {
            const status = params.get('spotify');
            if (status === 'connected') {
                this.showNotification('Spotify connected successfully!', 'success');
                this.updateServiceStatus('spotify', true);
            } else if (status === 'error') {
                this.showNotification('Failed to connect Spotify', 'error');
            }
            // Clean up URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        
        if (params.has('apple')) {
            const status = params.get('apple');
            if (status === 'connected') {
                this.showNotification('Apple Music connected successfully!', 'success');
                this.updateServiceStatus('apple', true);
            } else if (status === 'error') {
                this.showNotification('Failed to connect Apple Music', 'error');
            }
            // Clean up URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }
    
    async loadAllData() {
        // Load all data in parallel
        await Promise.all([
            this.loadTodos(),
            this.loadCalendar(),
            this.loadEmails(),
            this.loadGithub(),
            this.loadNews(),
            this.loadWeather(),
            this.loadDashboards()
        ]);
        
        this.updateAllCounts();
    }
    
    async loadNewJoke() {
        try {
            const response = await fetch('/api/joke');
            if (response.ok) {
                const data = await response.json();
                const jokeEl = document.getElementById('joke-content');
                if (jokeEl) {
                    jokeEl.textContent = data.joke || 'No joke available';
                    jokeEl.dataset.jokeId = data.id || 'unknown'; // Store joke ID for feedback
                }
            }
        } catch (error) {
            console.error('Error loading joke:', error);
            const jokeEl = document.getElementById('joke-content');
            if (jokeEl) {
                jokeEl.textContent = 'Failed to load joke 😅';
            }
        }
    }
    
    readJokeAloud() {
        const jokeEl = document.getElementById('joke-content');
        if (jokeEl && jokeEl.textContent) {
            this.speakText(jokeEl.textContent);
        }
    }
    
    async giveJokeFeedback(sentiment) {
        const jokeEl = document.getElementById('joke-content');
        if (!jokeEl) return;
        
        const jokeId = jokeEl.dataset.jokeId || 'unknown';
        const joke = jokeEl.textContent;
        
        // Store feedback for AI training
        if (!this.feedbackData.jokes) {
            this.feedbackData.jokes = {};
        }
        this.feedbackData.jokes[jokeId] = {
            joke: joke,
            sentiment: sentiment,
            timestamp: new Date().toISOString()
        };
        this.saveFeedbackToStorage();
        
        // Visual feedback
        const feedbackMsg = {
            'up': '👍 Great joke! Loading another...',
            'neutral': '👌 Okay! Loading another...',
            'down': '👎 Noted! Loading another...'
        }[sentiment] || 'Loading another...';
        
        jokeEl.textContent = feedbackMsg;
        
        // Load new joke after brief delay
        setTimeout(() => this.loadNewJoke(), 1000);
        
        console.log(`Joke feedback recorded: ${sentiment}`);
    }
    
    // TODOS
    async loadTodos() {
        try {
            // By default, don't include completed tasks
            const response = await fetch('/api/tasks?include_completed=false');
            if (response.ok) {
                const data = await response.json();
                this.todos = data.tasks || [];
                this.renderTodos();
                this.renderOverviewTasks();
            }
        } catch (error) {
            console.error('Error loading todos:', error);
        }
    }
    
    renderTodos() {
        const grid = document.getElementById('todos-grid');
        if (!grid) return;
        
        if (this.todos.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">✅</div>
                    <h3 class="text-xl font-semibold mb-2">No tasks</h3>
                    <p class="text-gray-400">All caught up!</p>
                </div>
            `;
            return;
        }
        
        // Add filter buttons
        const priorities = [...new Set(this.todos.map(t => t.priority).filter(Boolean))];
        const sources = [...new Set(this.todos.map(t => t.source).filter(Boolean))];
        
        const filters = `
            <div class="mb-4 flex gap-2 flex-wrap col-span-full">
                <button onclick="dataLoader.filterTodos('all')" 
                        class="todo-filter-btn px-3 py-1 bg-blue-600 rounded text-sm">All</button>
                <button onclick="dataLoader.filterTodos('active')" 
                        class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Active</button>
                <button onclick="dataLoader.filterTodos('completed')" 
                        class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Completed</button>
                ${priorities.map(p => 
                    `<button onclick="dataLoader.filterTodos('priority-${p}')" 
                             class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">${p}</button>`
                ).join('')}
                ${sources.map(s => 
                    `<button onclick="dataLoader.filterTodos('source-${s}')" 
                             class="todo-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">${this.escapeHtml(s)}</button>`
                ).join('')}
            </div>
        `;
        
        const html = this.todos.map(todo => {
            const feedback = this.feedbackData[`todo-${todo.id}`] || null;
            const isCompleted = todo.status === 'completed';
            const isStarted = todo.status === 'in_progress';
            const isDeleted = todo.status === 'deleted';
            
            return `
            <div class="dashboard-card bg-gray-800 rounded-xl p-6 border border-gray-700 cursor-pointer todo-item" 
                 data-status="${todo.status || 'pending'}"
                 data-priority="${todo.priority || ''}"
                 data-source="${todo.source || ''}"
                 onclick="dataLoader.showTodoDetail('${this.escapeHtml(todo.id)}')">
                <div class="flex items-start gap-3">
                    <div class="flex flex-col gap-1" onclick="event.stopPropagation()">
                        <label class="flex items-center gap-1 text-xs text-gray-400" title="Mark as started">
                            <input type="checkbox" ${isStarted ? 'checked' : ''} 
                                   onclick="dataLoader.toggleTodoStarted('${this.escapeHtml(todo.id)}')"
                                   class="w-4 h-4 rounded">
                            <span>Started</span>
                        </label>
                        <label class="flex items-center gap-1 text-xs text-gray-400" title="Mark as done">
                            <input type="checkbox" ${isCompleted ? 'checked' : ''} 
                                   onclick="dataLoader.toggleTodo('${this.escapeHtml(todo.id)}')"
                                   class="w-4 h-4 rounded">
                            <span>Done</span>
                        </label>
                    </div>
                    <div class="flex-1">
                        <h3 class="font-semibold text-white mb-1 ${isCompleted ? 'line-through opacity-60' : ''}">
                            ${isStarted && !isCompleted ? '🚀 ' : ''}${this.escapeHtml(todo.title)}
                        </h3>
                        ${todo.description ? `<p class="text-sm text-gray-400 mb-2">${this.escapeHtml(todo.description)}</p>` : ''}
                        <div class="flex flex-wrap gap-2 text-xs mb-3">
                            ${todo.priority ? `<span class="bg-${this.getPriorityColor(todo.priority)}-600 px-2 py-1 rounded">${todo.priority}</span>` : ''}
                            ${todo.due_date ? `<span class="bg-gray-700 px-2 py-1 rounded">📅 ${this.formatDate(todo.due_date)}</span>` : ''}
                            ${todo.source ? `<span class="bg-blue-700 px-2 py-1 rounded">${this.escapeHtml(todo.source)}</span>` : ''}
                            ${todo.source_url ? `<span class="bg-purple-700 px-2 py-1 rounded">🔗 Linked</span>` : ''}
                        </div>
                        <div class="flex gap-1 pt-2 border-t border-gray-700" onclick="event.stopPropagation()">
                            <button onclick="dataLoader.deleteTodo('${this.escapeHtml(todo.id)}')" 
                                    class="px-2 py-1 rounded text-xs bg-red-700 hover:bg-red-600" 
                                    title="Delete & never show again">🗑️ Delete</button>
                            <button onclick="dataLoader.giveFeedback('todo', '${this.escapeHtml(todo.id)}', 'up')" 
                                    class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                                    title="I like this">👍</button>
                            <button onclick="dataLoader.giveFeedback('todo', '${this.escapeHtml(todo.id)}', 'neutral')" 
                                    class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                                    title="Neutral">👌</button>
                            <button onclick="dataLoader.giveFeedback('todo', '${this.escapeHtml(todo.id)}', 'down')" 
                                    class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                                    title="Not relevant">👎</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = filters + html;
    }
    
    async filterTodos(filter) {
        const items = document.querySelectorAll('.todo-item');
        const buttons = document.querySelectorAll('.todo-filter-btn');
        
        buttons.forEach(btn => {
            btn.classList.remove('bg-blue-600');
            btn.classList.add('bg-gray-700');
        });
        
        event.target.classList.remove('bg-gray-700');
        event.target.classList.add('bg-blue-600');
        
        // If filtering by completed, reload tasks with include_completed=true
        if (filter === 'completed') {
            try {
                const response = await fetch('/api/tasks?include_completed=true');
                if (response.ok) {
                    const data = await response.json();
                    this.todos = data.tasks || [];
                    this.renderTodos();
                    // After re-rendering, re-apply the filter visually
                    setTimeout(() => {
                        document.querySelectorAll('.todo-item').forEach(item => {
                            item.style.display = item.dataset.status === 'completed' ? 'block' : 'none';
                        });
                    }, 100);
                    return;
                }
            } catch (error) {
                console.error('Error loading completed tasks:', error);
            }
        } else if (filter === 'all' || filter === 'active') {
            // Reload without completed tasks for all/active filters
            try {
                const response = await fetch('/api/tasks?include_completed=false');
                if (response.ok) {
                    const data = await response.json();
                    this.todos = data.tasks || [];
                    this.renderTodos();
                    
                    if (filter === 'active') {
                        // After re-rendering, show only active tasks
                        setTimeout(() => {
                            document.querySelectorAll('.todo-item').forEach(item => {
                                const status = item.dataset.status;
                                item.style.display = (status === 'pending' || status === 'in_progress') ? 'block' : 'none';
                            });
                        }, 100);
                    }
                    return;
                }
            } catch (error) {
                console.error('Error loading tasks:', error);
            }
        }
        
        // For other filters (priority, source), just filter visible items
        items.forEach(item => {
            let show = false;
            const status = item.dataset.status;
            
            if (filter === 'all') {
                show = true;
            } else if (filter === 'active') {
                // Active = pending or in_progress (not completed or deleted)
                show = status === 'pending' || status === 'in_progress';
            } else if (filter === 'completed') {
                show = status === 'completed';
            } else if (filter.startsWith('priority-')) {
                const priority = filter.replace('priority-', '');
                show = item.dataset.priority === priority;
            } else if (filter.startsWith('source-')) {
                const source = filter.replace('source-', '');
                show = item.dataset.source === source;
            }
            
            item.style.display = show ? 'block' : 'none';
        });
    }
    
    async deleteTodo(id) {
        if (!confirm('Delete this task? It will never appear again.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/tasks/${id}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                // Remove from local array
                this.todos = this.todos.filter(t => t.id !== id);
                this.renderTodos();
                this.updateAllCounts();
            }
        } catch (error) {
            console.error('Error deleting todo:', error);
            alert('Failed to delete task');
        }
    }
    
    renderOverviewTasks() {
        const container = document.getElementById('overview-tasks');
        if (!container) return;
        
        const topTasks = this.todos
            .filter(t => t.status !== 'completed' && t.status !== 'deleted')
            .slice(0, 5);
        
        if (topTasks.length === 0) {
            container.innerHTML = '<p class="text-gray-400">No pending tasks</p>';
            return;
        }
        
        container.innerHTML = topTasks.map(todo => `
            <div class="flex items-center gap-2 text-sm">
                <input type="checkbox" class="w-4 h-4 rounded">
                <span class="text-gray-300">${this.escapeHtml(todo.title)}</span>
            </div>
        `).join('');
    }
    
    // CALENDAR
    async loadCalendar() {
        try {
            const response = await fetch('/api/calendar');
            if (response.ok) {
                const data = await response.json();
                this.calendar = data.events || [];
                this.renderCalendar();
                this.renderOverviewCalendar();
                this.startUpcomingEventMonitor();
            }
        } catch (error) {
            console.error('Error loading calendar:', error);
        }
    }
    
    renderCalendar() {
        const container = document.getElementById('calendar-content');
        if (!container) return;
        
        if (this.calendar.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <div class="text-6xl mb-4">📅</div>
                    <h3 class="text-xl font-semibold mb-2">No events</h3>
                    <p class="text-gray-400">Your calendar is clear</p>
                </div>
            `;
            return;
        }
        
        // Add current time indicator and upcoming event banner
        const now = new Date();
        const upcomingEvent = this.getUpcomingEvent();
        
        let header = `
            <div class="mb-6 bg-gradient-to-r from-blue-900 to-purple-900 rounded-xl p-6 border border-blue-700">
                <div class="flex justify-between items-center mb-4">
                    <div>
                        <div class="text-sm text-gray-300">Current Time</div>
                        <div class="text-3xl font-bold" id="current-time">${this.formatCurrentTime()}</div>
                    </div>
                    <div class="text-6xl">🕐</div>
                </div>
                ${upcomingEvent ? `
                    <div class="border-t border-blue-700 pt-4 mt-4">
                        <div class="text-sm text-blue-300 mb-2">🔔 UPCOMING EVENT</div>
                        <div class="flex justify-between items-start">
                            <div class="flex-1">
                                <h3 class="text-xl font-semibold text-white mb-1">${this.escapeHtml(upcomingEvent.summary || upcomingEvent.title)}</h3>
                                <div class="text-sm text-gray-300 mb-2">
                                    ⏰ ${this.formatEventTime(upcomingEvent)} 
                                    <span class="text-yellow-400 font-semibold">(${this.getTimeUntil(upcomingEvent)})</span>
                                </div>
                                ${upcomingEvent.location ? `<div class="text-sm text-gray-400 mb-2">📍 ${this.escapeHtml(upcomingEvent.location)}</div>` : ''}
                                ${this.extractMeetingLink(upcomingEvent) ? `
                                    <a href="${this.extractMeetingLink(upcomingEvent)}" target="_blank"
                                       class="inline-flex items-center gap-2 bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg text-sm font-semibold">
                                        🎥 Join Meeting
                                    </a>
                                ` : ''}
                            </div>
                            <button onclick="dataLoader.dismissEventAlert('${upcomingEvent.event_id}')" 
                                    class="ml-4 text-gray-400 hover:text-white">
                                ✕
                            </button>
                        </div>
                    </div>
                ` : '<div class="text-center text-gray-400 border-t border-blue-700 pt-4 mt-4">No upcoming events</div>'}
            </div>
        `;
        
        // Group events by day
        const grouped = this.groupEventsByDay(this.calendar);
        
        container.innerHTML = header + Object.entries(grouped).map(([day, events]) => `
            <div class="mb-6">
                <h3 class="text-xl font-bold mb-3 text-blue-400">${day}</h3>
                <div class="space-y-2">
                    ${events.map(event => {
                        const meetingLink = this.extractMeetingLink(event);
                        return `
                        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 cursor-pointer hover:border-gray-600"
                             onclick="dataLoader.showEventDetail('${this.escapeHtml(event.event_id)}')">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-semibold text-white">${this.escapeHtml(event.summary || event.title)}</h4>
                                    ${event.location ? `<p class="text-sm text-gray-400">📍 ${this.escapeHtml(event.location)}</p>` : ''}
                                    ${event.summary_ai ? `
                                        <div class="mt-2 p-2 bg-gray-700 rounded text-sm">
                                            <div class="text-xs text-gray-400 mb-1">AI Summary:</div>
                                            <div class="text-white">${this.escapeHtml(event.summary_ai)}</div>
                                        </div>
                                    ` : ''}
                                    <div class="flex gap-2 mt-2" onclick="event.stopPropagation()">
                                        ${meetingLink ? `
                                            <a href="${meetingLink}" target="_blank"
                                               class="inline-flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded">
                                                🎥 Join
                                            </a>
                                        ` : ''}
                                        <button data-item-type="calendar" 
                                                data-item-id="${this.escapeHtml(event.event_id)}" 
                                                data-item-data="${this.escapeHtml(JSON.stringify(event))}"
                                                onclick="dataLoader.summarizeItemFromButton(this)"
                                                class="inline-flex items-center gap-1 text-xs bg-purple-600 hover:bg-purple-700 px-2 py-1 rounded"
                                                title="Summarize and scan for tasks">
                                            🤖 AI
                                        </button>
                                    </div>
                                </div>
                                <span class="text-sm text-blue-400">${this.formatEventTime(event)}</span>
                            </div>
                        </div>
                    `;
                    }).join('')}
                </div>
            </div>
        `).join('');
        
        // Update current time every second
        this.startClockUpdate();
    }
    
    renderOverviewCalendar() {
        const container = document.getElementById('overview-calendar');
        if (!container) return;
        
        const today = new Date().toDateString();
        const todayEvents = this.calendar.filter(e => {
            const startDate = e.start && e.start.dateTime ? e.start.dateTime : e.start;
            const eventDate = new Date(startDate).toDateString();
            return eventDate === today;
        });
        
        if (todayEvents.length === 0) {
            container.innerHTML = '<p class="text-gray-400">No events today</p>';
            return;
        }
        
        container.innerHTML = todayEvents.map(event => `
            <div class="flex justify-between items-center text-sm">
                <span class="text-gray-300">${this.escapeHtml(event.summary || event.title)}</span>
                <span class="text-blue-400">${this.formatEventTime(event)}</span>
            </div>
        `).join('');
    }
    
    // EMAILS
    async loadEmails(forceRefresh = false) {
        try {
            // Add cache-busting parameter if force refresh
            const url = forceRefresh 
                ? `/api/email?refresh=${Date.now()}` 
                : '/api/email';
            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                // Filter out noreply and no-reply emails
                this.emails = (data.emails || []).filter(email => {
                    const sender = (email.sender || email.from || '').toLowerCase();
                    return !sender.includes('noreply') && !sender.includes('no-reply');
                });
                
                const unreadCount = this.emails.filter(e => !e.read).length;
                const readCount = this.emails.filter(e => e.read).length;
                console.log(`Loaded ${this.emails.length} emails (${unreadCount} unread, ${readCount} read)`);
                this.renderEmails();
            }
        } catch (error) {
            console.error('Error loading emails:', error);
        }
    }
    
        async refreshEmails() {
        this.showNotification('Refreshing emails...', 'info');
        await this.loadEmails(true); // Force refresh with cache busting
        this.updateAllCounts();
        this.showNotification('Emails refreshed!', 'success');
    }
    
    showScanEmailsModal() {
        const today = new Date();
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        
        const content = `
            <div class="space-y-4">
                <p class="text-gray-300">Scan your emails for tasks and action items. This will analyze emails from a specific date range and create todos for any emails that require action.</p>
                
                <div class="bg-yellow-900/30 border border-yellow-600 rounded-lg p-4">
                    <p class="text-yellow-200 text-sm">⚠️ <strong>Note:</strong> This uses AI to analyze emails and will only create tasks for emails with clear action items, not newsletters or spam.</p>
                </div>
                
                <div class="space-y-3">
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">Start Date</label>
                        <input type="date" id="scan-start-date" 
                               value="${thirtyDaysAgo.toISOString().split('T')[0]}"
                               max="${today.toISOString().split('T')[0]}"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">End Date</label>
                        <input type="date" id="scan-end-date" 
                               value="${today.toISOString().split('T')[0]}"
                               max="${today.toISOString().split('T')[0]}"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">Max Emails to Scan</label>
                        <select id="scan-max-emails" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                            <option value="50">50 emails</option>
                            <option value="100" selected>100 emails</option>
                            <option value="200">200 emails</option>
                            <option value="500">500 emails</option>
                        </select>
                    </div>
                </div>
                
                <div class="flex gap-3 pt-4">
                    <button onclick="dataLoader.startEmailScan()" 
                            class="flex-1 bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg font-semibold">
                        🔍 Start Scan
                    </button>
                    <button onclick="closeModal()" 
                            class="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg font-semibold">
                        Cancel
                    </button>
                </div>
                
                <div id="scan-progress" class="hidden mt-4">
                    <div class="bg-gray-700 rounded-lg p-4">
                        <div class="flex items-center gap-3 mb-2">
                            <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-400"></div>
                            <span class="text-purple-400 font-semibold">Scanning emails...</span>
                        </div>
                        <p id="scan-status" class="text-sm text-gray-400">Initializing...</p>
                        <div id="scan-results" class="mt-3 text-sm"></div>
                    </div>
                </div>
            </div>
        `;
        
        showModal('Scan Emails for Tasks', content);
    }
    
    async startEmailScan() {
        const startDate = document.getElementById('scan-start-date').value;
        const endDate = document.getElementById('scan-end-date').value;
        const maxEmails = document.getElementById('scan-max-emails').value;
        
        if (!startDate || !endDate) {
            this.showNotification('Please select both start and end dates', 'error');
            return;
        }
        
        // Show progress section
        const progressDiv = document.getElementById('scan-progress');
        const statusDiv = document.getElementById('scan-status');
        const resultsDiv = document.getElementById('scan-results');
        progressDiv.classList.remove('hidden');
        
        statusDiv.textContent = `Scanning up to ${maxEmails} emails from ${startDate} to ${endDate}...`;
        
        try {
            const response = await fetch('/api/email/scan-for-tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    start_date: startDate,
                    end_date: endDate,
                    max_emails: parseInt(maxEmails)
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                statusDiv.textContent = `✅ Scan complete!`;
                resultsDiv.innerHTML = `
                    <div class="space-y-2">
                        <p class="text-green-400">✅ Scanned ${data.emails_scanned} emails</p>
                        <p class="text-blue-400">📋 Created ${data.tasks_created} new tasks</p>
                        <p class="text-gray-400">⏭️ Skipped ${data.emails_skipped} emails (spam/newsletters)</p>
                        <p class="text-yellow-400">⚠️ ${data.tasks_skipped} duplicate tasks avoided</p>
                    </div>
                    <button onclick="closeModal(); dataLoader.loadTodos();" 
                            class="mt-4 w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg font-semibold">
                        View Tasks
                    </button>
                `;
                this.showNotification(`Created ${data.tasks_created} tasks from ${data.emails_scanned} emails`, 'success');
            } else {
                const error = await response.json();
                statusDiv.textContent = `❌ Error: ${error.detail || 'Failed to scan emails'}`;
                resultsDiv.innerHTML = '';
            }
        } catch (error) {
            statusDiv.textContent = `❌ Error: ${error.message}`;
            resultsDiv.innerHTML = '';
            this.showNotification('Failed to scan emails', 'error');
        }
    }
    
    renderEmails() {
        const grid = document.getElementById('emails-grid');
        if (!grid) {
            console.error('emails-grid element not found');
            return;
        }
        
        console.log(`Rendering ${this.emails.length} emails`);
        
        if (this.emails.length === 0) {
            grid.innerHTML = `
                <div class="text-center py-12">
                    <div class="text-6xl mb-4">📧</div>
                    <h3 class="text-xl font-semibold mb-2">Inbox Zero!</h3>
                    <p class="text-gray-400">No unread emails</p>
                </div>
            `;
            return;
        }
        
        // Add filter buttons
        const labels = [...new Set(this.emails.flatMap(e => e.labels || []))];
        
        const filters = `
            <div class="mb-4 flex gap-2 flex-wrap col-span-full">
                <input type="text" id="email-search" placeholder="Search emails..." 
                       oninput="dataLoader.filterEmails()" 
                       class="flex-1 max-w-md bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm text-white">
                <button onclick="dataLoader.filterEmails('all')" 
                        class="email-filter-btn px-3 py-1 bg-blue-600 rounded text-sm">All</button>
                <button onclick="dataLoader.filterEmails('unread')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Unread</button>
                <button onclick="dataLoader.filterEmails('read')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Read</button>
                <button onclick="dataLoader.filterEmails('has-todos')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">Has Tasks</button>
                <button onclick="dataLoader.filterEmails('high-priority')" 
                        class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">High Priority</button>
                <button onclick="dataLoader.filterEmails('high-risk')" 
                        class="email-filter-btn px-3 py-1 bg-red-700 rounded text-sm hover:bg-red-600">⚠️ High Risk</button>
                <button onclick="dataLoader.filterEmails('safe')" 
                        class="email-filter-btn px-3 py-1 bg-green-700 rounded text-sm hover:bg-green-600">✓ Safe</button>
                ${labels.map(label => 
                    `<button onclick="dataLoader.filterEmails('label-${this.escapeHtml(label)}')" 
                             class="email-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">${this.escapeHtml(label)}</button>`
                ).join('')}
            </div>
        `;
        
        const html = this.emails.map(email => {
            const feedback = this.feedbackData[`email-${email.id}`] || null;
            const readClass = email.read ? 'opacity-70 bg-gray-800' : 'bg-gray-750 border-blue-500/30';
            const readIndicator = email.read ? 
                '<span class="text-gray-500 text-xs">✓ Read</span>' : 
                '<span class="flex items-center gap-1 text-blue-400 text-xs font-semibold"><span class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>UNREAD</span>';
            const smartTag = this.getSmartTagForEmail(email);
            
            // Format the date/time nicely
            const emailDate = email.received_date || email.date;
            const timeAgo = this.getTimeAgo(emailDate);
            
            // Trust Layer Badge - on-demand scanning only
            // Auto-fetch trust report (backend caches safe emails to avoid rescanning)
            let riskBadge = '<span class="text-xs bg-gray-600 px-2 py-1 rounded" title="Analyzing email security...">⏳ Analyzing...</span>';
            if (trustUI) {
                trustUI.getTrustReport(email).then(report => {
                    if (report && report.score !== undefined) {
                        const badge = trustUI.getTrustBadge(report.score, report.risk_level);
                        const container = document.querySelector(`[onclick*="showEmailDetail('${this.escapeHtml(email.id)}')"] .trust-badge-container`);
                        if (container) {
                            container.innerHTML = badge;
                        }
                    }
                }).catch(err => {
                    console.error('Trust report fetch failed for', email.id, err);
                    // Show scan button on error
                    const container = document.querySelector(`[onclick*="showEmailDetail('${this.escapeHtml(email.id)}')"] .trust-badge-container`);
                    if (container) {
                        container.innerHTML = trustUI.getTrustBadge(null, null);
                    }
                });
            }
            
            // Smart tag with tooltip
            let smartTagHtml = '';
            if (smartTag) {
                const domain = email.sender.split('@')[1] || email.sender;
                smartTagHtml = `<span class="text-xs bg-purple-600 px-2 py-1 rounded whitespace-nowrap cursor-help" title="Auto-tagged based on your feedback patterns from ${domain}">${smartTag}</span>`;
            }
            
            return `
            <div class="rounded-lg p-4 border border-gray-700 cursor-pointer hover:border-gray-600 ${readClass}"
                 onclick="dataLoader.showEmailDetail('${this.escapeHtml(email.id)}')">
                <div class="flex justify-between items-start mb-2">
                    <div class="flex gap-2 items-center flex-1">
                        ${readIndicator}
                        <span class="font-semibold text-white">${this.escapeHtml(email.sender)}</span>
                        <span class="text-xs text-gray-500 ml-auto">${timeAgo}</span>
                    </div>
                </div>
                <div class="flex justify-between items-start mb-2">
                    <h4 class="font-medium text-gray-200 flex-1">${this.escapeHtml(email.subject)}</h4>
                    <div class="flex gap-2 items-center ml-2">
                        <div class="trust-badge-container">${riskBadge}</div>
                        ${smartTagHtml}
                        ${email.has_todos ? '<span class="text-xs bg-orange-600 px-2 py-1 rounded whitespace-nowrap cursor-help" title="This email has associated tasks">📋 Tasks</span>' : ''}
                        ${email.priority === 'high' ? '<span class="text-xs bg-red-600 px-2 py-1 rounded whitespace-nowrap cursor-help" title="High priority email">High</span>' : ''}
                    </div>
                </div>
                ${email.snippet ? `<p class="text-sm text-gray-400 line-clamp-2 mb-2">${this.escapeHtml(email.snippet)}</p>` : ''}
                ${email.labels && email.labels.length > 0 ? `
                    <div class="flex gap-2 mt-2 mb-2 flex-wrap">
                        ${email.labels.map(label => 
                            `<span class="text-xs bg-blue-600 px-2 py-1 rounded">${this.escapeHtml(label)}</span>`
                        ).join('')}
                    </div>
                ` : ''}
                ${email.summary ? `
                    <div class="mt-2 p-2 bg-gray-700 rounded text-sm">
                        <div class="text-xs text-gray-400 mb-1">AI Summary:</div>
                        <div class="text-white">${this.escapeHtml(email.summary)}</div>
                    </div>
                ` : ''}
                <div class="flex gap-1 pt-2 border-t border-gray-700" onclick="event.stopPropagation()">
                    <button data-item-type="email" 
                            data-item-id="${this.escapeHtml(email.id)}" 
                            data-item-data="${this.escapeHtml(JSON.stringify(email))}"
                            onclick="dataLoader.summarizeItemFromButton(this)"
                            class="px-2 py-1 rounded text-xs bg-purple-600 hover:bg-purple-700" 
                            title="Summarize and scan for tasks">🤖 AI</button>
                    ${email.is_whitelisted ? 
                        '<span class="px-2 py-1 text-xs bg-green-600 rounded">✓ Trusted Sender</span>' :
                        `<button onclick="dataLoader.markEmailAsSafe('${this.escapeHtml(email.sender)}')" 
                                class="px-2 py-1 rounded text-xs bg-gray-700 hover:bg-green-600" 
                                title="Mark this sender as safe/trusted">✓ Mark Safe</button>`
                    }
                    <button onclick="dataLoader.giveFeedback('email', '${this.escapeHtml(email.id)}', 'up')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                            title="Important email">👍</button>
                    <button onclick="dataLoader.giveFeedback('email', '${this.escapeHtml(email.id)}', 'neutral')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                            title="Neutral">👌</button>
                    <button onclick="dataLoader.giveFeedback('email', '${this.escapeHtml(email.id)}', 'down')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                            title="Spam/Not relevant">👎</button>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = filters + html;
    }
    
    filterEmails(filter = null) {
        const searchInput = document.getElementById('email-search');
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        
        // Update button states
        document.querySelectorAll('.email-filter-btn').forEach(btn => {
            btn.classList.remove('bg-blue-600', 'bg-red-700', 'bg-green-700');
            if (btn.textContent.includes('High Risk')) {
                btn.classList.add('bg-red-700');
            } else if (btn.textContent.includes('Safe')) {
                btn.classList.add('bg-green-700');
            } else {
                btn.classList.add('bg-gray-700');
            }
        });
        
        if (filter && event && event.target) {
            event.target.classList.remove('bg-gray-700', 'bg-red-700', 'bg-green-700');
            event.target.classList.add('bg-blue-600');
        }
        
        // Get all email cards - they're divs with onclick="dataLoader.showEmailDetail"
        const emailGrid = document.getElementById('emails-grid');
        if (!emailGrid) return;
        
        const emailCards = emailGrid.querySelectorAll('[onclick*="showEmailDetail"]');
        
        emailCards.forEach((card, index) => {
            const email = this.emails[index];
            if (!email) {
                card.style.display = 'none';
                return;
            }
            
            let visible = true;
            
            // Apply filter
            if (filter === 'unread') {
                visible = !email.read;
            } else if (filter === 'read') {
                visible = email.read;
            } else if (filter === 'has-todos') {
                visible = email.has_todos;
            } else if (filter === 'high-priority') {
                visible = email.priority === 'high';
            } else if (filter === 'high-risk') {
                visible = (email.risk_score || 0) >= 7;
            } else if (filter === 'safe') {
                visible = (email.risk_score || 0) < 3;
            } else if (filter && filter.startsWith('label-')) {
                const label = filter.substring(6);
                visible = email.labels && email.labels.includes(label);
            }
            
            // Apply search
            if (searchTerm && visible) {
                const searchableText = `${email.sender} ${email.subject} ${email.snippet || ''}`.toLowerCase();
                visible = searchableText.includes(searchTerm);
            }
            
            card.style.display = visible ? 'block' : 'none';
        });
    }
    
    // DASHBOARDS
    async loadDashboards() {
        try {
            const response = await fetch('/api/dashboards');
            if (response.ok) {
                const data = await response.json();
                this.dashboards = data.data || {};
                this.renderDashboards();
            }
        } catch (error) {
            console.error('Error loading dashboards:', error);
        }
    }
    
    renderDashboards() {
        const grid = document.getElementById('dashboards-grid');
        if (!grid) return;
        
        const dashboards = this.dashboards;
        if (!dashboards.projects && !dashboards.websites) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">📊</div>
                    <h3 class="text-xl font-semibold mb-2">No dashboards</h3>
                    <p class="text-gray-400">No projects or websites found</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        // Projects section
        if (dashboards.projects && dashboards.projects.details) {
            html += `
                <div class="col-span-full mb-6">
                    <h3 class="text-xl font-bold mb-4">Projects (${dashboards.projects.total})</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        ${dashboards.projects.details.map(project => {
                            const statusColors = {
                                'running': 'bg-green-500',
                                'stopped': 'bg-gray-500',
                                'error': 'bg-red-500'
                            };
                            const statusColor = statusColors[project.status] || 'bg-gray-500';
                            
                            return `
                                <div class="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition-colors">
                                    <div class="flex justify-between items-start mb-3">
                                        <div class="flex-1">
                                            <div class="flex items-center gap-2 mb-1">
                                                <span class="w-2 h-2 ${statusColor} rounded-full"></span>
                                                <h4 class="font-semibold text-white">${this.escapeHtml(project.name)}</h4>
                                            </div>
                                            ${project.brand ? `<div class="text-xs text-gray-400">${this.escapeHtml(project.brand)}</div>` : ''}
                                        </div>
                                    </div>
                                    
                                    ${project.description ? `<p class="text-sm text-gray-400 mb-3">${this.escapeHtml(project.description)}</p>` : ''}
                                    
                                    <div class="flex flex-wrap gap-2 text-xs">
                                        <span class="px-2 py-1 bg-gray-700 rounded">${project.type || 'Unknown'}</span>
                                        ${project.port ? `<span class="px-2 py-1 bg-blue-900 rounded">Port ${project.port}</span>` : ''}
                                    </div>
                                    
                                    ${project.url ? `
                                        <div class="mt-3 pt-3 border-t border-gray-700">
                                            <a href="${project.url}" target="_blank" 
                                               class="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1">
                                                🔗 Open Project
                                            </a>
                                        </div>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }
        
        // Websites section
        if (dashboards.websites && dashboards.websites.details) {
            html += `
                <div class="col-span-full">
                    <h3 class="text-xl font-bold mb-4">Websites (${dashboards.websites.total})</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        ${dashboards.websites.details.map(website => {
                            const statusColors = {
                                'online': 'bg-green-500',
                                'offline': 'bg-red-500'
                            };
                            const statusColor = statusColors[website.status] || 'bg-gray-500';
                            
                            return `
                                <div class="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition-colors">
                                    <div class="flex justify-between items-start mb-3">
                                        <div class="flex-1">
                                            <div class="flex items-center gap-2 mb-1">
                                                <span class="w-2 h-2 ${statusColor} rounded-full"></span>
                                                <h4 class="font-semibold text-white">${this.escapeHtml(website.name)}</h4>
                                            </div>
                                            ${website.brand ? `<div class="text-xs text-gray-400">${this.escapeHtml(website.brand)}</div>` : ''}
                                        </div>
                                    </div>
                                    
                                    <div class="flex flex-wrap gap-2 text-xs mb-3">
                                        <span class="px-2 py-1 bg-gray-700 rounded">${website.deployment_type || 'Unknown'}</span>
                                        ${website.build_status ? `<span class="px-2 py-1 bg-purple-900 rounded">${website.build_status}</span>` : ''}
                                    </div>
                                    
                                    ${website.live_url ? `
                                        <div class="pt-3 border-t border-gray-700">
                                            <a href="${website.live_url}" target="_blank" 
                                               class="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1">
                                                🌐 Visit Website
                                            </a>
                                        </div>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }
        
        grid.innerHTML = html;
    }
    
    // GITHUB
    async loadGithub() {
        try {
            const response = await fetch('/api/github');
            if (response.ok) {
                const data = await response.json();
                this.github = data;
                this.renderGithub();
            }
        } catch (error) {
            console.error('Error loading GitHub:', error);
        }
    }
    
    renderGithub() {
        const container = document.getElementById('github-content');
        if (!container) return;
        
        const { repos = [], issues = [], prs = [] } = this.github;
        
        container.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 text-center">
                    <div class="text-3xl font-bold text-blue-400">${repos.length}</div>
                    <div class="text-sm text-gray-400">Repositories</div>
                </div>
                <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 text-center">
                    <div class="text-3xl font-bold text-green-400">${prs.length}</div>
                    <div class="text-sm text-gray-400">Pull Requests</div>
                </div>
                <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 text-center">
                    <div class="text-3xl font-bold text-yellow-400">${issues.length}</div>
                    <div class="text-sm text-gray-400">Issues</div>
                </div>
            </div>
            
            <div class="space-y-6">
                ${repos.length > 0 ? `
                    <div>
                        <h3 class="text-xl font-bold mb-3">Recent Repositories</h3>
                        <div class="space-y-2">
                            ${repos.slice(0, 5).map(repo => `
                                <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
                                    <a href="${repo.url}" target="_blank" class="font-semibold text-blue-400 hover:underline">
                                        ${this.escapeHtml(repo.name)}
                                    </a>
                                    ${repo.description ? `<p class="text-sm text-gray-400 mt-1">${this.escapeHtml(repo.description)}</p>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    // NEWS
    async loadNews() {
        try {
            const includeRead = this.showReadArticles ? 'true' : 'false';
            const response = await fetch(`/api/news?include_read=${includeRead}`);
            if (response.ok) {
                const data = await response.json();
                this.news = data.articles || [];
                this.renderNews();
            }
        } catch (error) {
            console.error('Error loading news:', error);
        }
    }
    
    renderNews() {
        const grid = document.getElementById('news-grid');
        if (!grid) return;
        
        if (this.news.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">📰</div>
                    <h3 class="text-xl font-semibold mb-2">No news</h3>
                    <p class="text-gray-400">Check back later</p>
                </div>
            `;
            return;
        }
        
        // Get unique categories for filtering
        const categories = [...new Set(this.news.map(item => item.category).filter(Boolean))];
        
        const categoryFilters = categories.length > 0 ? `
            <div class="mb-4 flex gap-2 flex-wrap col-span-full">
                <button onclick="dataLoader.filterNews('all')" 
                        class="news-filter-btn px-3 py-1 bg-blue-600 rounded text-sm">All</button>
                ${categories.map(cat => 
                    `<button onclick="dataLoader.filterNews('${this.escapeHtml(cat)}')" 
                             class="news-filter-btn px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">${this.escapeHtml(cat)}</button>`
                ).join('')}
                <button onclick="dataLoader.toggleShowReadArticles()" 
                        class="ml-auto px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">
                    ${this.showReadArticles ? '📖 Hide Read' : '📚 Show All'}
                </button>
            </div>
        ` : `
            <div class="mb-4 flex justify-end col-span-full">
                <button onclick="dataLoader.toggleShowReadArticles()" 
                        class="px-3 py-1 bg-gray-700 rounded text-sm hover:bg-gray-600">
                    ${this.showReadArticles ? '📖 Hide Read' : '📚 Show All'}
                </button>
            </div>
        `;
        
        // Generate accordion items
        const html = this.news.map(article => {
            // Process description to extract and render images and links properly
            let cleanDesc = article.description || article.snippet || '';
            
            // Skip if no content at all
            if (!cleanDesc && !article.title) {
                return '';
            }
            
            // First decode HTML entities
            const textarea = document.createElement('textarea');
            textarea.innerHTML = cleanDesc;
            cleanDesc = textarea.value;
            
            // Extract image URLs before removing tags
            const imgMatches = cleanDesc.match(/<img[^>]+src="([^">]+)"/g);
            const imgUrls = imgMatches ? imgMatches.map(match => {
                const srcMatch = match.match(/src="([^"]+)"/);
                return srcMatch ? srcMatch[1] : null;
            }).filter(Boolean) : [];
            
            // Extract and preserve links with proper styling
            const links = [];
            cleanDesc = cleanDesc.replace(/<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)<\/a>/gi, (match, url, text) => {
                links.push({ url, text });
                return `[[LINK_${links.length - 1}]]`;
            });
            
            // Remove img tags
            cleanDesc = cleanDesc.replace(/<img[^>]*>/gi, '');
            
            // Remove all other HTML tags
            cleanDesc = cleanDesc.replace(/<[^>]*>/gi, '');
            
            // Clean up extra whitespace
            cleanDesc = cleanDesc.trim().replace(/\s+/g, ' ');
            
            // Restore links with proper HTML
            links.forEach((link, index) => {
                const linkHtml = `<a href="${link.url}" target="_blank" class="text-blue-400 hover:text-blue-300 underline" onclick="event.stopPropagation()">${link.text}</a>`;
                cleanDesc = cleanDesc.replace(`[[LINK_${index}]]`, linkHtml);
            });
            
            const feedback = this.feedbackData[`news-${article.id}`] || null;
            const isRead = article.is_read || false;
            
            return `
            <div class="news-accordion-item bg-gray-800 border-b border-gray-700 last:border-b-0 news-item ${isRead ? 'news-read' : 'news-unread'}" 
                 data-category="${this.escapeHtml(article.category || '')}"
                 data-article-id="${article.id}">
                <!-- Collapsed Header - Just the title -->
                <div class="news-accordion-header p-4 cursor-pointer hover:bg-gray-750 transition-colors flex items-center justify-between"
                     onclick="dataLoader.toggleNewsAccordion('${article.id}')">
                    <div class="flex items-center gap-3 flex-1">
                        ${isRead ? '<span class="text-gray-500 text-sm">✓</span>' : '<span class="text-green-400 text-sm">●</span>'}
                        <h3 class="font-semibold text-white">${this.escapeHtml(article.title)}</h3>
                    </div>
                    <div class="flex items-center gap-4">
                        <span class="text-purple-400 text-sm">${this.escapeHtml(article.source || 'News')}</span>
                        <svg class="news-chevron w-5 h-5 text-gray-400 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </div>
                </div>
                
                <!-- Expanded Content (hidden by default) -->
                <div class="news-accordion-content hidden border-t border-gray-700">
                    <div class="p-6 bg-gray-850">
                        <div class="flex gap-2 items-center mb-3">
                            ${article.category ? `<span class="text-xs bg-purple-600 px-2 py-0.5 rounded">${this.escapeHtml(article.category)}</span>` : ''}
                            <span class="text-gray-500 text-sm">${this.formatDate(article.published_at)}</span>
                        </div>
                        
                        ${imgUrls.length > 0 ? `
                            <div class="mb-4 grid ${imgUrls.length > 1 ? 'grid-cols-2' : 'grid-cols-1'} gap-2">
                                ${imgUrls.slice(0, 4).map(imgUrl => `
                                    <img src="${imgUrl}" alt="${this.escapeHtml(article.title)}" 
                                         class="w-full rounded-lg ${imgUrls.length === 1 ? 'h-64' : 'h-48'} object-cover cursor-pointer"
                                         onerror="this.style.display='none'"
                                         onclick="event.stopPropagation(); window.open('${imgUrl}', '_blank')">
                                `).join('')}
                            </div>
                        ` : ''}
                        
                        ${cleanDesc ? `
                            <div class="prose prose-invert max-w-none mb-4">
                                <p class="text-gray-300 leading-relaxed">${cleanDesc}</p>
                            </div>
                        ` : ''}
                        
                        <!-- Action Buttons -->
                        <div class="flex gap-3 items-center pt-4 border-t border-gray-700" onclick="event.stopPropagation()">
                            <a href="${article.url}" target="_blank" 
                               class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors flex items-center gap-2"
                               onclick="dataLoader.markArticleRead('${article.id}')">
                                <span>Read Full Article</span>
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                                </svg>
                            </a>
                            
                            <div class="flex gap-1 ml-auto">
                                <button onclick="dataLoader.giveFeedback('news', '${article.id}', 'up')" 
                                        class="feedback-btn px-3 py-2 rounded-lg text-sm ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                                        title="Interesting">👍 Interesting</button>
                                <button onclick="dataLoader.giveFeedback('news', '${article.id}', 'neutral')" 
                                        class="feedback-btn px-3 py-2 rounded-lg text-sm ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                                        title="Neutral">👌 OK</button>
                                <button onclick="dataLoader.giveFeedback('news', '${article.id}', 'down')" 
                                        class="feedback-btn px-3 py-2 rounded-lg text-sm ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                                        title="Not interested">👎 Not for me</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = categoryFilters + '<div class="col-span-full space-y-0 border border-gray-700 rounded-xl overflow-hidden">' + html + '</div>';
    }
    
    toggleNewsAccordion(articleId) {
        const item = document.querySelector(`[data-article-id="${articleId}"]`);
        if (!item) return;
        
        const content = item.querySelector('.news-accordion-content');
        const chevron = item.querySelector('.news-chevron');
        
        // Don't close other accordions - let user open multiple articles
        // Removed the code that was closing all other accordions
        
        // Toggle this accordion
        content.classList.toggle('hidden');
        chevron.classList.toggle('rotate-180');
        
        // Don't auto-mark as read when opening - only when clicking "Read Full Article"
        // This way users can preview without marking as read
    }
    
    async markArticleRead(articleId) {
        try {
            const response = await fetch(`/api/news/${articleId}/read`, {
                method: 'POST'
            });
            
            if (response.ok) {
                // Update UI to show as read
                const item = document.querySelector(`[data-article-id="${articleId}"]`);
                if (item) {
                    item.classList.remove('news-unread');
                    item.classList.add('news-read');
                    
                    // Update the status badge
                    const header = item.querySelector('.news-accordion-header');
                    const statusBadge = header.querySelector('.text-green-400');
                    if (statusBadge) {
                        statusBadge.className = 'text-xs text-gray-500';
                        statusBadge.textContent = '✓ Read';
                    }
                }
                
                // Update the article in our data
                const article = this.news.find(a => a.id === articleId);
                if (article) {
                    article.is_read = true;
                }
                
                // Don't auto-hide - let the user continue reading and close manually
                // Articles will be filtered on next news load/refresh
                this.updateAllCounts();
            }
        } catch (error) {
            console.error('Error marking article as read:', error);
        }
    }
    
    toggleShowReadArticles() {
        this.showReadArticles = !this.showReadArticles;
        
        // Reload news with updated filter
        this.loadNews();
    }
    
    filterNews(category) {
        const items = document.querySelectorAll('.news-item');
        const buttons = document.querySelectorAll('.news-filter-btn');
        
        buttons.forEach(btn => {
            btn.classList.remove('bg-blue-600');
            btn.classList.add('bg-gray-700');
        });
        
        event.target.classList.remove('bg-gray-700');
        event.target.classList.add('bg-blue-600');
        
        items.forEach(item => {
            if (category === 'all' || item.dataset.category === category) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    async showNewsSourcesModal() {
        try {
            // Fetch current news sources
            const response = await fetch('/api/news-sources');
            const data = await response.json();
            const sources = data.sources || [];
            
            const modal = document.createElement('div');
            modal.id = 'news-sources-modal';
            modal.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto';
            modal.onclick = (e) => {
                if (e.target === modal) modal.remove();
            };
            
            modal.innerHTML = `
                <div class="bg-gray-800 rounded-xl p-6 max-w-4xl w-full my-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-2xl font-bold">Manage News Sources</h3>
                        <button onclick="document.getElementById('news-sources-modal').remove()" 
                                class="text-gray-400 hover:text-white text-2xl leading-none">
                            ×
                        </button>
                    </div>
                    
                    <div class="max-h-[calc(90vh-12rem)] overflow-y-auto pr-2 space-y-6">
                        <div>
                            <h4 class="text-lg font-semibold mb-3">Add Custom Source</h4>
                            <form id="add-source-form" class="grid grid-cols-3 gap-3">
                                <input type="text" id="source-name" placeholder="Source Name" 
                                       class="bg-gray-700 border border-gray-600 rounded px-3 py-2" required>
                                <input type="url" id="source-url" placeholder="RSS Feed URL" 
                                       class="bg-gray-700 border border-gray-600 rounded px-3 py-2" required>
                                <button type="submit" 
                                        class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded">
                                    ➕ Add Source
                                </button>
                            </form>
                        </div>
                        
                        <div>
                            <h4 class="text-lg font-semibold mb-3">Active Sources (${sources.filter(s => s.is_active).length})</h4>
                            <div class="space-y-2">
                                ${sources.map(source => `
                                    <div class="bg-gray-700 rounded-lg p-3 flex items-center justify-between">
                                        <div class="flex-1">
                                            <div class="font-semibold">${this.escapeHtml(source.name)}</div>
                                            <div class="text-xs text-gray-400">${source.category || 'general'} ${source.is_custom ? '(Custom)' : ''}</div>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <label class="flex items-center gap-1">
                                                <input type="checkbox" 
                                                       ${source.is_active ? 'checked' : ''}
                                                       onchange="dataLoader.toggleNewsSource(${source.id}, this.checked)"
                                                       class="w-4 h-4 rounded">
                                                <span class="text-xs">Active</span>
                                            </label>
                                            ${source.is_custom ? `
                                                <button onclick="dataLoader.deleteNewsSource(${source.id})" 
                                                        class="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs">
                                                    🗑️
                                                </button>
                                            ` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-6 pt-4 border-t border-gray-700">
                        <button onclick="document.getElementById('news-sources-modal').remove(); dataLoader.loadNews();" 
                                class="w-full bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                            Save & Reload News
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Handle add source form
            document.getElementById('add-source-form').onsubmit = async (e) => {
                e.preventDefault();
                const name = document.getElementById('source-name').value;
                const url = document.getElementById('source-url').value;
                
                await this.addNewsSource(name, url);
                modal.remove();
                this.showNewsSourcesModal();
            };
        } catch (error) {
            console.error('Error showing news sources modal:', error);
            this.showNotification('⚠️ Error loading news sources');
        }
    }
    
    async addNewsSource(name, url) {
        try {
            const response = await fetch('/api/news-sources', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, url, category: 'custom' })
            });
            
            if (response.ok) {
                this.showNotification(`✅ Added news source: ${name}`);
            } else {
                this.showNotification('⚠️ Error adding news source');
            }
        } catch (error) {
            console.error('Error adding news source:', error);
            this.showNotification('⚠️ Error adding news source');
        }
    }
    
    async toggleNewsSource(sourceId, isActive) {
        try {
            const response = await fetch(`/api/news-sources/${sourceId}/toggle`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: isActive })
            });
            
            if (response.ok) {
                this.showNotification(isActive ? '✅ Source activated' : '⏸️ Source deactivated');
            }
        } catch (error) {
            console.error('Error toggling news source:', error);
        }
    }
    
    async deleteNewsSource(sourceId) {
        if (!confirm('Delete this news source?')) return;
        
        try {
            const response = await fetch(`/api/news-sources/${sourceId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showNotification('🗑️ News source deleted');
                document.getElementById('news-sources-modal').remove();
                this.showNewsSourcesModal();
            }
        } catch (error) {
            console.error('Error deleting news source:', error);
            this.showNotification('⚠️ Error deleting news source');
        }
    }
    
    // WEATHER
    async loadWeather() {
        try {
            const response = await fetch('/api/weather');
            if (response.ok) {
                const data = await response.json();
                this.weather = data;
                this.renderWeather();
            }
        } catch (error) {
            console.error('Error loading weather:', error);
        }
    }
    
    renderWeather() {
        const container = document.getElementById('weather-content');
        if (!container) return;
        
        // Weather API returns flat structure: temperature, description, icon, location, forecast[]
        if (!this.weather || !this.weather.temperature) {
            container.innerHTML = '<p class="text-gray-400 text-center py-12">Weather data unavailable</p>';
            return;
        }
        
        const iconMap = {
            '01d': '☀️', '01n': '🌙',
            '02d': '⛅', '02n': '☁️',
            '03d': '☁️', '03n': '☁️',
            '04d': '☁️', '04n': '☁️',
            '09d': '🌧️', '09n': '🌧️',
            '10d': '🌦️', '10n': '🌧️',
            '11d': '⛈️', '11n': '⛈️',
            '13d': '🌨️', '13n': '🌨️',
            '50d': '🌫️', '50n': '🌫️'
        };
        
        const currentIcon = iconMap[this.weather.icon] || '🌤️';
        
        container.innerHTML = `
            <div class="bg-gray-800 rounded-xl p-8 border border-gray-700 text-center mb-6">
                <div class="text-6xl mb-4">${currentIcon}</div>
                <div class="text-5xl font-bold mb-2">${this.weather.temperature}</div>
                <div class="text-xl text-gray-400 mb-2">${this.weather.description || 'Clear'}</div>
                ${this.weather.location ? `<div class="text-sm text-gray-500">📍 ${this.weather.location}</div>` : ''}
                <div class="grid grid-cols-2 gap-4 mt-6 text-sm">
                    ${this.weather.feels_like ? `<div><span class="text-gray-400">Feels Like:</span> ${this.weather.feels_like}</div>` : ''}
                    ${this.weather.humidity ? `<div><span class="text-gray-400">Humidity:</span> ${this.weather.humidity}%</div>` : ''}
                    ${this.weather.wind_speed ? `<div><span class="text-gray-400">Wind:</span> ${this.weather.wind_speed}</div>` : ''}
                    ${this.weather.pressure ? `<div><span class="text-gray-400">Pressure:</span> ${this.weather.pressure}</div>` : ''}
                </div>
            </div>
            
            ${this.weather.forecast && this.weather.forecast.length > 0 ? `
                <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                    ${this.weather.forecast.map(day => {
                        const dayIcon = iconMap[day.icon] || '☀️';
                        return `
                        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 text-center">
                            <div class="text-sm text-gray-400 mb-2">${day.day || day.date}</div>
                            <div class="text-3xl mb-2">${dayIcon}</div>
                            <div class="font-semibold text-white mb-1">${day.high}° / ${day.low}°</div>
                            <div class="text-xs text-gray-400">${day.condition}</div>
                            ${day.precipitation_chance ? `<div class="text-xs text-blue-400 mt-1">💧 ${day.precipitation_chance}%</div>` : ''}
                        </div>
                    `;
                    }).join('')}
                </div>
            ` : ''}
        `;
    }
    
    async loadNotes() {
        try {
            const response = await fetch('/api/notes');
            if (response.ok) {
                const data = await response.json();
                this.notes = data.notes || [];
                this.notesStats = {
                    obsidian_count: data.obsidian_count || 0,
                    gdrive_count: data.gdrive_count || 0,
                    total_todos_found: data.total_todos_found || 0,
                    tasks_created: data.tasks_created || 0
                };
                this.renderNotes();
            }
        } catch (error) {
            console.error('Error loading notes:', error);
        }
    }
    
    refreshNotes() {
        this.loadNotes();
    }
    
    // Helper function to call summarizeItem from button with data attributes
    async summarizeItemFromButton(button) {
        try {
            const itemType = button.getAttribute('data-item-type');
            const itemId = button.getAttribute('data-item-id');
            const itemDataStr = button.getAttribute('data-item-data');
            const itemData = JSON.parse(itemDataStr);
            
            await this.summarizeItem(itemType, itemId, itemData);
        } catch (error) {
            console.error('Error parsing item data:', error);
            this.showNotification('❌ Error: Invalid item data', 'error');
        }
    }
    
    async summarizeItem(itemType, itemId, itemData) {
        try {
            // Show loading indicator - add spinning wheel next to button
            const button = event.target.closest('button');
            const originalText = button.innerHTML;
            button.disabled = true;
            
            // Create and add spinner
            const spinner = document.createElement('span');
            spinner.className = 'ai-loading-spinner';
            spinner.innerHTML = '&nbsp;<svg class="inline-block animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>';
            button.appendChild(spinner);
            
            // Prepare content based on item type
            let content = '';
            let title = '';
            let metadata = {};
            
            if (itemType === 'note') {
                content = itemData.preview || '';
                title = itemData.title || 'Untitled Note';
                metadata = {
                    url: itemData.url || itemData.path,
                    source: itemData.source
                };
            } else if (itemType === 'email') {
                content = itemData.body || itemData.snippet || '';
                title = itemData.subject || 'No Subject';
                metadata = {
                    id: itemData.id,
                    from: itemData.from
                };
            } else if (itemType === 'calendar') {
                content = itemData.description || '';
                title = itemData.summary || itemData.title || 'Untitled Event';
                metadata = {
                    id: itemData.id,
                    start: itemData.start,
                    end: itemData.end
                };
            }
            
            // Call API
            const response = await fetch('/api/ai/summarize/item', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    item_type: itemType,
                    item_id: itemId,
                    content: content,
                    title: title,
                    metadata: metadata
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update the item with the summary
                if (itemType === 'note') {
                    const note = this.notes.find(n => (n.doc_id === itemId || n.relative_path === itemId));
                    if (note) {
                        note.summary = data.summary;
                    }
                    this.renderNotes();
                } else if (itemType === 'email') {
                    const email = this.emails.find(e => e.id === itemId);
                    if (email) {
                        email.summary = data.summary;
                    }
                    this.renderEmails();
                } else if (itemType === 'calendar') {
                    const event = this.calendar.find(e => e.id === itemId);
                    if (event) {
                        event.summary_ai = data.summary;
                    }
                    this.renderCalendar();
                }
                
                // Show success message
                const message = `✅ Summary complete! ${data.tasks_created > 0 ? `Created ${data.tasks_created} task${data.tasks_created > 1 ? 's' : ''}.` : 'No tasks found.'}`;
                this.showNotification(message, 'success');
                
                // Reload tasks if any were created
                if (data.tasks_created > 0) {
                    this.loadTodos();
                }
            } else {
                const error = await response.json();
                this.showNotification(`❌ Error: ${error.detail || 'Failed to summarize'}`, 'error');
            }
            
            // Remove spinner and restore button
            const loadingSpinner = button.querySelector('.ai-loading-spinner');
            if (loadingSpinner) loadingSpinner.remove();
            button.disabled = false;
            
        } catch (error) {
            console.error('Error summarizing item:', error);
            this.showNotification('❌ Error summarizing item', 'error');
            
            // Remove spinner and restore button
            const errorButton = event.target.closest('button');
            const errorSpinner = errorButton.querySelector('.ai-loading-spinner');
            if (errorSpinner) errorSpinner.remove();
            errorButton.disabled = false;
        }
    }
    
    renderNotes() {
        const container = document.getElementById('notes-grid');
        const statsContainer = document.getElementById('notes-stats');
        
        if (!container) return;
        
        // Render stats
        if (statsContainer && this.notesStats) {
            statsContainer.innerHTML = `
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">Obsidian Notes</div>
                    <div class="text-2xl font-bold text-white">${this.notesStats.obsidian_count}</div>
                </div>
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">Google Drive Notes</div>
                    <div class="text-2xl font-bold text-white">${this.notesStats.gdrive_count}</div>
                </div>
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">TODOs Found</div>
                    <div class="text-2xl font-bold text-purple-400">${this.notesStats.total_todos_found}</div>
                </div>
                <div class="bg-gray-800 rounded-lg p-4">
                    <div class="text-gray-400 text-sm">Tasks Created</div>
                    <div class="text-2xl font-bold text-green-400">${this.notesStats.tasks_created}</div>
                </div>
            `;
        }
        
        // Render notes grid
        if (!this.notes || this.notes.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-center py-12 col-span-3">No recent notes found</p>';
            return;
        }
        
        container.innerHTML = this.notes.map(note => {
            const sourceIcon = note.source === 'obsidian' ? '📓' : '📄';
            const sourceLabel = note.source === 'obsidian' ? 'Obsidian' : 'Google Drive';
            const sourceColor = note.source === 'obsidian' ? 'purple' : 'blue';
            
            // Format link
            let noteLink = '#';
            if (note.source === 'obsidian' && note.path) {
                // Use obsidian:// protocol for local notes
                const vaultName = note.path.split('/').find(p => p && p !== '..' && p !== '.');
                const relPath = note.path.split('/').slice(-2).join('/');
                noteLink = `obsidian://open?vault=${encodeURIComponent(vaultName || 'MyVault')}&file=${encodeURIComponent(relPath)}`;
            } else if (note.source === 'gdrive' && note.url) {
                noteLink = note.url;
            }
            
            return `
                <div class="bg-gray-800 rounded-lg p-5 hover:bg-gray-750 transition-all duration-200">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <span class="text-2xl">${sourceIcon}</span>
                            <span class="px-2 py-1 rounded text-xs font-medium bg-${sourceColor}-500/20 text-${sourceColor}-400">
                                ${sourceLabel}
                            </span>
                            ${note.todo_count ? `<span class="px-2 py-1 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400">${note.todo_count} TODOs</span>` : ''}
                        </div>
                        <span class="text-xs text-gray-500">${note.modified || 'Recently updated'}</span>
                    </div>
                    
                    <h3 class="text-lg font-semibold text-white mb-2 line-clamp-2">
                        ${note.title || 'Untitled Note'}
                    </h3>
                    
                    ${note.tags && note.tags.length > 0 ? `
                        <div class="flex flex-wrap gap-1 mb-2">
                            ${note.tags.slice(0, 3).map(tag => `
                                <span class="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-300">#${tag}</span>
                            `).join('')}
                            ${note.tags.length > 3 ? `<span class="text-xs text-gray-500">+${note.tags.length - 3} more</span>` : ''}
                        </div>
                    ` : ''}
                    
                    <p class="text-gray-400 text-sm mb-3 line-clamp-3">
                        ${note.preview || 'No preview available'}
                    </p>
                    
                    ${note.word_count ? `<div class="text-xs text-gray-500 mb-3">${note.word_count} words</div>` : ''}
                    
                    ${note.summary ? `
                        <div class="mb-3 p-3 bg-gray-700 rounded text-sm">
                            <div class="text-xs text-gray-400 mb-1">AI Summary:</div>
                            <div class="text-white">${this.escapeHtml(note.summary)}</div>
                        </div>
                    ` : ''}
                    
                    <div class="flex gap-2">
                        <a href="${noteLink}" target="_blank" 
                           class="flex-1 px-3 py-2 bg-${sourceColor}-600 hover:bg-${sourceColor}-700 rounded text-sm font-medium text-center transition-all duration-200">
                            Open Note
                        </a>
                        <button data-item-type="note" 
                                data-item-id="${note.doc_id || note.relative_path}" 
                                data-item-data="${this.escapeHtml(JSON.stringify(note))}"
                                onclick="dataLoader.summarizeItemFromButton(this)"
                                class="px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded text-sm font-medium transition-all duration-200 flex items-center gap-1"
                                title="Summarize and scan for tasks">
                            🤖 AI
                        </button>
                        ${note.todo_count ? `
                            <button onclick="dataLoader.loadTodos(); showSection('todos');" 
                                    class="px-3 py-2 bg-yellow-600 hover:bg-yellow-700 rounded text-sm font-medium transition-all duration-200">
                                View Tasks
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    // UPDATE COUNTS
    updateAllCounts() {
        // Todos - count active (pending or in_progress)
        const todosCount = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted').length;
        this.updateBadge('todos-count', todosCount);
        this.updateStat('stat-tasks', todosCount);
        
        // Emails - only count unread
        const unreadEmailsCount = this.emails.filter(e => !e.read).length;
        this.updateBadge('emails-count', unreadEmailsCount);
        this.updateStat('stat-emails', unreadEmailsCount);
        
        // News - only count unread
        const unreadNewsCount = this.news.filter(n => !n.is_read).length;
        this.updateBadge('news-count', unreadNewsCount);
        this.updateStat('stat-news', unreadNewsCount);
    }
    
    updateBadge(id, count) {
        const badge = document.getElementById(id);
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'block' : 'none';
        }
    }
    
    updateStat(id, count) {
        const stat = document.getElementById(id);
        if (stat) {
            stat.textContent = count;
        }
    }
    
    // HELPER METHODS
    getPriorityColor(priority) {
        const colors = { high: 'red', medium: 'yellow', low: 'green' };
        return colors[priority?.toLowerCase()] || 'gray';
    }
    
    formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        
        if (date.toDateString() === today.toDateString()) return 'Today';
        if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    
    getTimeAgo(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    
    formatTime(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        });
    }
    
    formatEventTime(event) {
        if (event.is_all_day) return 'All day';
        if (event.time) return event.time;
        const start = event.start && event.start.dateTime ? event.start.dateTime : event.start;
        return this.formatTime(start);
    }
    
    groupEventsByDay(events) {
        const grouped = {};
        events.forEach(event => {
            const start = event.start && event.start.dateTime ? event.start.dateTime : event.start;
            const day = this.formatDate(start);
            if (!grouped[day]) grouped[day] = [];
            grouped[day].push(event);
        });
        return grouped;
    }
    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // CALENDAR HELPERS
    formatCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        });
    }
    
    startClockUpdate() {
        setInterval(() => {
            const clockEl = document.getElementById('current-time');
            if (clockEl) {
                clockEl.textContent = this.formatCurrentTime();
            }
        }, 1000);
    }
    
    getUpcomingEvent() {
        const now = new Date();
        const upcomingEvents = this.calendar
            .filter(event => {
                const startDate = event.start && event.start.dateTime ? new Date(event.start.dateTime) : new Date(event.start);
                return startDate > now;
            })
            .sort((a, b) => {
                const aStart = a.start && a.start.dateTime ? new Date(a.start.dateTime) : new Date(a.start);
                const bStart = b.start && b.start.dateTime ? new Date(b.start.dateTime) : new Date(b.start);
                return aStart - bStart;
            });
        
        return upcomingEvents[0] || null;
    }
    
    getTimeUntil(event) {
        const now = new Date();
        const startDate = event.start && event.start.dateTime ? new Date(event.start.dateTime) : new Date(event.start);
        const diff = startDate - now;
        
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) return `in ${days} day${days > 1 ? 's' : ''}`;
        if (hours > 0) return `in ${hours} hour${hours > 1 ? 's' : ''}`;
        if (minutes > 0) return `in ${minutes} minute${minutes > 1 ? 's' : ''}`;
        return 'starting now';
    }
    
    extractMeetingLink(event) {
        // Check description for Zoom/Google Meet/Teams links
        const text = (event.description || '') + ' ' + (event.location || '');
        
        // Zoom
        const zoomMatch = text.match(/https?:\/\/[\w-]*\.?zoom\.us\/[^\s]*/i);
        if (zoomMatch) return zoomMatch[0];
        
        // Google Meet
        const meetMatch = text.match(/https?:\/\/meet\.google\.com\/[^\s]*/i);
        if (meetMatch) return meetMatch[0];
        
        // Microsoft Teams
        const teamsMatch = text.match(/https?:\/\/teams\.microsoft\.com\/[^\s]*/i);
        if (teamsMatch) return teamsMatch[0];
        
        // Check if location is a URL
        if (event.location && event.location.startsWith('http')) {
            return event.location;
        }
        
        return null;
    }
    
    startUpcomingEventMonitor() {
        // Clear existing timer
        if (this.upcomingEventTimer) {
            clearInterval(this.upcomingEventTimer);
        }
        
        // Check every minute for upcoming events
        this.upcomingEventTimer = setInterval(() => {
            this.checkUpcomingEvents();
        }, 60000); // Check every minute
        
        // Check immediately
        this.checkUpcomingEvents();
    }
    
    checkUpcomingEvents() {
        const now = new Date();
        const alertThresholds = [15, 10, 5, 2]; // Alert at 15, 10, 5, and 2 minutes before
        
        this.calendar.forEach(event => {
            const startDate = event.start && event.start.dateTime ? new Date(event.start.dateTime) : new Date(event.start);
            const minutesUntil = Math.floor((startDate - now) / 60000);
            
            // Check if we should alert for this event
            if (alertThresholds.includes(minutesUntil) && !this.alertedEvents.has(`${event.event_id}-${minutesUntil}`)) {
                this.alertedEvents.add(`${event.event_id}-${minutesUntil}`);
                this.showEventAlert(event, minutesUntil);
            }
        });
    }
    
    showEventAlert(event, minutesUntil) {
        const meetingLink = this.extractMeetingLink(event);
        const eventTitle = event.summary || event.title;
        const location = event.location || '';
        
        // Create visual alert
        const alertDiv = document.createElement('div');
        alertDiv.id = `alert-${event.event_id}`;
        alertDiv.className = 'fixed top-4 right-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl shadow-2xl p-6 max-w-md z-50 bounce-thrice';
        alertDiv.innerHTML = `
            <div class="flex justify-between items-start mb-3">
                <h3 class="text-xl font-bold">🔔 Event Starting Soon!</h3>
                <button onclick="dataLoader.dismissAlert('${event.event_id}')" class="text-white hover:text-gray-200">✕</button>
            </div>
            <p class="font-semibold text-lg mb-2">${this.escapeHtml(eventTitle)}</p>
            <p class="text-sm mb-2">⏰ Starting in ${minutesUntil} minute${minutesUntil > 1 ? 's' : ''}</p>
            ${location ? `<p class="text-sm mb-3">📍 ${this.escapeHtml(location)}</p>` : ''}
            <div class="flex gap-2 mb-3">
                ${meetingLink ? `
                    <a href="${meetingLink}" target="_blank" 
                       class="flex-1 bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg text-center font-semibold">
                        🎥 Join Now
                    </a>
                ` : ''}
                <button onclick="dataLoader.dismissAlert('${event.event_id}')" 
                        class="flex-1 bg-white bg-opacity-20 hover:bg-opacity-30 px-4 py-2 rounded-lg font-semibold">
                    Dismiss
                </button>
            </div>
            <div class="border-t border-white border-opacity-20 pt-3 mt-3">
                <button onclick="dataLoader.startVoiceResponse('${event.event_id}')" 
                        class="w-full bg-white bg-opacity-20 hover:bg-opacity-30 px-4 py-2 rounded-lg flex items-center justify-center gap-2">
                    🎤 Voice Response
                </button>
            </div>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Speak the alert using AI voice
        this.speakEventAlert(eventTitle, minutesUntil, location);
        
        // Auto-dismiss after 30 seconds
        setTimeout(() => {
            this.dismissAlert(event.event_id);
        }, 30000);
    }
    
    speakEventAlert(eventTitle, minutesUntil, location) {
        if (!this.speechSynthesis) return;
        
        const message = `Hello! You have an event starting in ${minutesUntil} minute${minutesUntil > 1 ? 's' : ''}. ${eventTitle}. ${location ? `The location is ${location}.` : ''} Would you like to join?`;
        
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.rate = 0.9; // Slightly slower for clarity
        utterance.pitch = 1.0;
        utterance.volume = 0.8;
        
        // Try to use a more natural voice
        const voices = this.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.name.includes('Samantha') || v.name.includes('Karen') || v.name.includes('Daniel'));
        if (preferredVoice) {
            utterance.voice = preferredVoice;
        }
        
        this.speechSynthesis.speak(utterance);
    }
    
    startVoiceResponse(eventId) {
        if (!this.voiceRecognition) {
            alert('Voice recognition is not supported in your browser.');
            return;
        }
        
        const alertDiv = document.getElementById(`alert-${eventId}`);
        if (alertDiv) {
            const btn = alertDiv.querySelector('button[onclick*="startVoiceResponse"]');
            if (btn) {
                btn.innerHTML = '🎤 Listening...';
                btn.classList.add('animate-pulse');
            }
        }
        
        this.voiceRecognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript.toLowerCase();
            console.log('Voice input:', transcript);
            
            if (transcript.includes('know') || transcript.includes('got it') || transcript.includes('on it')) {
                this.handleVoiceResponse(eventId, 'acknowledged');
            } else if (transcript.includes('not') || transcript.includes('skip') || transcript.includes('cancel')) {
                this.handleVoiceResponse(eventId, 'declined');
            } else {
                this.handleVoiceResponse(eventId, 'unclear');
            }
        };
        
        this.voiceRecognition.onerror = (event) => {
            console.error('Voice recognition error:', event.error);
            alert('Could not understand. Please try again.');
        };
        
        this.voiceRecognition.start();
    }
    
    handleVoiceResponse(eventId, response) {
        const event = this.calendar.find(e => e.event_id === eventId);
        const eventTitle = event ? (event.summary || event.title) : 'the event';
        
        let message = '';
        if (response === 'acknowledged') {
            message = `Great! I've noted that you're aware of ${eventTitle}. See you there!`;
        } else if (response === 'declined') {
            message = `Understood. I've noted that you won't be attending ${eventTitle}.`;
        } else {
            message = `I didn't quite catch that. Please try again or dismiss this alert.`;
        }
        
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.rate = 0.9;
        this.speechSynthesis.speak(utterance);
        
        if (response !== 'unclear') {
            setTimeout(() => {
                this.dismissAlert(eventId);
            }, 2000);
        }
    }
    
    dismissAlert(eventId) {
        const alertDiv = document.getElementById(`alert-${eventId}`);
        if (alertDiv) {
            alertDiv.remove();
        }
    }
    
    dismissEventAlert(eventId) {
        this.dismissAlert(eventId);
    }
    
    // DETAIL MODALS
    showTodoDetail(id) {
        const todo = this.todos.find(t => t.id === id);
        if (!todo) return;
        
        // Determine source icon
        const sourceIcon = {
            'email': '📧',
            'calendar': '📅',
            'note': '📝',
            'ticktick': '✓',
            'default': '📌'
        }[todo.source?.toLowerCase()] || '📌';
        
        const sourceButton = todo.source_url ? `
            <button onclick="openSourceContent('${this.escapeHtml(todo.id)}', '${this.escapeHtml(todo.source_url)}')" 
                    class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-semibold">
                🔗 View Original ${this.escapeHtml(todo.source_title || todo.source || 'Source')}
            </button>
        ` : '';
        
        const content = `
            <div class="space-y-4">
                <div class="flex items-center gap-3 mb-4">
                    <span class="text-3xl">${sourceIcon}</span>
                    <div>
                        <p class="text-xs font-semibold text-gray-400 uppercase">${this.escapeHtml(todo.source || 'Task')}</p>
                        <h1 class="text-2xl font-bold">${this.escapeHtml(todo.title)}</h1>
                    </div>
                </div>
                
                ${todo.description ? `<p class="text-gray-300 bg-gray-700 rounded-lg p-4">${this.escapeHtml(todo.description)}</p>` : ''}
                
                <div class="grid grid-cols-2 gap-3">
                    ${todo.priority ? `
                        <div class="bg-gray-700 rounded-lg p-3">
                            <p class="text-xs text-gray-400">Priority</p>
                            <p class="text-lg font-semibold">⚡ ${this.escapeHtml(todo.priority)}</p>
                        </div>
                    ` : ''}
                    ${todo.due_date ? `
                        <div class="bg-gray-700 rounded-lg p-3">
                            <p class="text-xs text-gray-400">Due Date</p>
                            <p class="text-lg font-semibold">📅 ${this.formatDate(todo.due_date)}</p>
                        </div>
                    ` : ''}
                </div>
                
                ${sourceButton}
                
                ${todo.source ? `
                    <div class="text-sm text-gray-400 border-t border-gray-700 pt-4">
                        <p>📌 Source: <span class="text-gray-300">${this.escapeHtml(todo.source_title || todo.source)}</span></p>
                    </div>
                ` : ''}
            </div>
        `;
        
        showModal('Task Details', content);
    }
    
    showEventDetail(id) {
        const event = this.calendar.find(e => e.event_id === id);
        if (!event) return;
        
        const start = event.start && event.start.dateTime ? event.start.dateTime : event.start;
        
        const content = `
            <div class="space-y-4">
                <h1 class="text-2xl font-bold">${this.escapeHtml(event.summary || event.title)}</h1>
                <p class="text-blue-400">${this.formatDate(start)} ${event.is_all_day ? '(All day)' : 'at ' + this.formatEventTime(event)}</p>
                ${event.location ? `<p class="text-gray-300">📍 ${this.escapeHtml(event.location)}</p>` : ''}
                ${event.description ? `<p class="text-gray-300">${this.escapeHtml(event.description)}</p>` : ''}
                ${event.organizer ? `<p class="text-gray-400 text-sm">Organizer: ${this.escapeHtml(event.organizer)}</p>` : ''}
                ${event.attendees && event.attendees.length > 0 ? `<p class="text-gray-400 text-sm">Attendees: ${event.attendees.length}</p>` : ''}
                ${event.calendar_url ? `<a href="${event.calendar_url}" target="_blank" class="text-blue-400 hover:underline text-sm">View in Google Calendar →</a>` : ''}
            </div>
        `;
        
        showModal('Event Details', content);
    }
    
    showEmailDetail(id) {
        const email = this.emails.find(e => e.id === id);
        if (!email) return;
        
        // Process email body to render HTML properly and extract text for reading
        let emailContent = email.body || email.snippet || 'No content available';
        let emailTextForReading = '';
        
        // Check if content contains HTML
        if (/<[^>]+>/.test(emailContent)) {
            // Create a temporary div to parse HTML
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = emailContent;
            
            // Extract text for voice reading (without HTML)
            emailTextForReading = tempDiv.textContent || tempDiv.innerText || '';
            
            // Style the HTML content for display
            tempDiv.querySelectorAll('*').forEach(el => {
                el.style.maxWidth = '100%';
                el.style.wordWrap = 'break-word';
            });
            
            tempDiv.querySelectorAll('img').forEach(img => {
                img.style.maxWidth = '100%';
                img.style.height = 'auto';
                img.style.borderRadius = '8px';
                img.style.marginTop = '8px';
                img.style.marginBottom = '8px';
            });
            
            tempDiv.querySelectorAll('a').forEach(link => {
                link.className = 'text-blue-400 hover:text-blue-300 underline';
                link.target = '_blank';
            });
            
            emailContent = tempDiv.innerHTML;
        } else {
            emailTextForReading = emailContent;
            emailContent = this.escapeHtml(emailContent).replace(/\n/g, '<br>');
        }
        
        const content = `
            <div class="space-y-4">
                <div class="border-b border-gray-700 pb-4">
                    <h1 class="text-2xl font-bold mb-2">${this.escapeHtml(email.subject)}</h1>
                    <p class="text-gray-400">From: ${this.escapeHtml(email.sender)}</p>
                    <p class="text-gray-400 text-sm">${this.formatDate(email.received_date || email.date || email.timestamp)}</p>
                    ${email.labels && email.labels.length > 0 ? `
                        <div class="flex gap-2 mt-2">
                            ${email.labels.map(label => 
                                `<span class="text-xs bg-blue-600 px-2 py-1 rounded">${this.escapeHtml(label)}</span>`
                            ).join('')}
                        </div>
                    ` : ''}
                </div>
                
                <div class="bg-gray-700 rounded-lg p-6 max-h-96 overflow-y-auto prose prose-invert max-w-none">
                    ${emailContent}
                </div>
                
                <div id="ai-analysis-section" class="bg-gray-800 rounded-lg p-4 border border-purple-600">
                    <div class="flex items-center justify-center gap-2 text-purple-400">
                        <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-400"></div>
                        <span>AI is analyzing this email...</span>
                    </div>
                </div>
                
                <div class="flex gap-2 pt-4 border-t border-gray-700">
                    ${email.gmail_url ? `
                        <button onclick="window.open('${email.gmail_url}', '_blank')" 
                                class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-semibold">
                            Open in Gmail
                        </button>
                    ` : ''}
                    <button onclick="closeModal()" 
                            class="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg font-semibold">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        showModal('Email', content);
        
        // Read email aloud and get AI analysis
        this.readAndAnalyzeEmail(email, emailTextForReading);
    }
    
    async readAndAnalyzeEmail(email, emailText) {
        // Prepare text for reading - subject + from + body
        const textToRead = `Email from ${email.sender}. Subject: ${email.subject}. ${emailText.substring(0, 500)}`;
        
        // Read email aloud
        this.speakText(textToRead);
        
        // Get AI analysis
        try {
            const response = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: `Analyze this email and suggest what I should do:

Subject: ${email.subject}
From: ${email.sender}
Date: ${email.date || email.timestamp || email.received_date}

${emailText.substring(0, 1500)}

Please provide:
1. Brief summary (2-3 sentences)
2. Key action items or requests
3. Suggested response or next steps
4. Priority level (High/Medium/Low)

Then ask me: "What would you like to do with this email?"`,
                    context: {
                        email_context: {
                            subject: email.subject,
                            sender: email.sender,
                            priority: email.priority,
                            has_todos: email.has_todos,
                            labels: email.labels
                        }
                    }
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                const aiAnalysis = data.response || data.message;
                
                // Update the analysis section
                const analysisSection = document.getElementById('ai-analysis-section');
                if (analysisSection) {
                    analysisSection.innerHTML = `
                        <div>
                            <h3 class="font-bold text-purple-400 mb-2 flex items-center gap-2">
                                <span>🤖</span>
                                <span>AI Analysis</span>
                            </h3>
                            <div class="text-gray-300 whitespace-pre-line mb-4">${this.escapeHtml(aiAnalysis)}</div>
                            <div class="flex gap-2 flex-wrap">
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'reply')" 
                                        class="bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded text-sm">
                                    📝 Reply
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'create-task')" 
                                        class="bg-green-600 hover:bg-green-700 px-3 py-2 rounded text-sm">
                                    ✅ Create Task
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'schedule')" 
                                        class="bg-purple-600 hover:bg-purple-700 px-3 py-2 rounded text-sm">
                                    📅 Schedule Follow-up
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'archive')" 
                                        class="bg-gray-600 hover:bg-gray-700 px-3 py-2 rounded text-sm">
                                    📦 Archive
                                </button>
                                <button onclick="dataLoader.handleEmailAction('${email.id}', 'delete')" 
                                        class="bg-red-600 hover:bg-red-700 px-3 py-2 rounded text-sm">
                                    🗑️ Delete
                                </button>
                            </div>
                        </div>
                    `;
                    
                    // Read the AI analysis aloud
                    this.speakText(aiAnalysis);
                }
            }
        } catch (error) {
            console.error('Error analyzing email:', error);
            const analysisSection = document.getElementById('ai-analysis-section');
            if (analysisSection) {
                analysisSection.innerHTML = `
                    <div class="text-red-400">
                        <p>❌ Failed to analyze email. Please try again.</p>
                    </div>
                `;
            }
        }
    }
    
    async handleEmailAction(emailId, action) {
        const email = this.emails.find(e => e.id === emailId);
        if (!email) return;
        
        switch(action) {
            case 'reply':
                if (email.gmail_url) {
                    window.open(email.gmail_url, '_blank');
                }
                this.showNotification('Opening Gmail to reply...', 'info');
                break;
                
            case 'create-task':
                // Create a task from the email
                const newTask = {
                    title: `Follow up: ${email.subject}`,
                    description: `Email from ${email.sender}`,
                    priority: email.priority || 'medium',
                    source: 'email'
                };
                this.todos.push(newTask);
                this.renderTodos();
                this.showNotification('Task created!', 'success');
                closeModal();
                break;
                
            case 'schedule':
                this.showNotification('Schedule follow-up (coming soon)', 'info');
                break;
                
            case 'archive':
                this.showNotification('Archiving email...', 'info');
                // TODO: Call API to archive
                closeModal();
                break;
                
            case 'delete':
                if (confirm('Are you sure you want to delete this email?')) {
                    this.showNotification('Deleting email...', 'info');
                    // TODO: Call API to delete
                    closeModal();
                }
                break;
        }
    }
    
    async toggleTodo(id) {
        const todo = this.todos.find(t => t.id === id);
        if (!todo) return;
        
        // Toggle between completed and pending
        const newStatus = todo.status === 'completed' ? 'pending' : 'completed';
        
        try {
            const response = await fetch(`/api/tasks/${encodeURIComponent(id)}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            if (response.ok) {
                // Update local state
                todo.status = newStatus;
                this.renderTodos();
                this.updateAllCounts();
            } else {
                console.error('Failed to update task status');
                alert('Failed to update task. Please try again.');
            }
        } catch (error) {
            console.error('Error updating task status:', error);
            alert('Failed to update task. Please try again.');
        }
    }
    
    async toggleTodoStarted(id) {
        const todo = this.todos.find(t => t.id === id);
        if (!todo) return;
        
        // Toggle between in_progress and pending (unless completed)
        if (todo.status === 'completed') return; // Don't toggle if already completed
        
        const newStatus = todo.status === 'in_progress' ? 'pending' : 'in_progress';
        
        try {
            const response = await fetch(`/api/tasks/${encodeURIComponent(id)}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            if (response.ok) {
                // Update local state
                todo.status = newStatus;
                this.renderTodos();
            } else {
                console.error('Failed to update task status');
                alert('Failed to update task. Please try again.');
            }
        } catch (error) {
            console.error('Error updating task status:', error);
            alert('Failed to update task. Please try again.');
        }
    }
    
    // AI ASSISTANT
    async loadAISuggestions() {
        try {
            // Generate suggestions from emails with has_todos flag
            const todoEmails = this.emails.filter(e => e.has_todos);
            
            this.aiSuggestions = todoEmails.map((email, idx) => ({
                id: `suggestion-${idx}`,
                title: `Follow up: ${email.subject}`,
                description: email.snippet || 'Review and create tasks from this email',
                priority: email.priority,
                source: 'email',
                email_id: email.id,
                action: 'create_task'
            }));
            
            // Add high priority emails
            const highPriority = this.emails.filter(e => e.priority === 'high' && !e.has_todos);
            highPriority.slice(0, 3).forEach((email, idx) => {
                this.aiSuggestions.push({
                    id: `priority-${idx}`,
                    title: `High Priority: ${email.subject}`,
                    description: email.snippet || 'This email needs your attention',
                    priority: 'high',
                    source: 'email',
                    email_id: email.id,
                    action: 'review'
                });
            });
            
            // Filter out tasks that already exist in todos
            this.aiSuggestions = this.aiSuggestions.filter(suggestion => {
                // Check if a similar task already exists
                const exists = this.todos.some(todo => {
                    // Check for exact title match
                    if (todo.title && suggestion.title && 
                        todo.title.toLowerCase() === suggestion.title.toLowerCase()) {
                        return true;
                    }
                    // Check if the email subject is in the todo title or description
                    if (suggestion.email_id && this.emails) {
                        const email = this.emails.find(e => e.id === suggestion.email_id);
                        if (email && email.subject) {
                            const subject = email.subject.toLowerCase();
                            const todoTitle = (todo.title || '').toLowerCase();
                            const todoDesc = (todo.description || '').toLowerCase();
                            // Check if email subject is substantially present in todo
                            if (todoTitle.includes(subject) || subject.includes(todoTitle) ||
                                todoDesc.includes(subject)) {
                                return true;
                            }
                        }
                    }
                    return false;
                });
                return !exists;
            });
            
            // Generate personalized random suggestion
            this.generatePersonalizedSuggestion();
            
            // Generate overview summary
            await this.generateOverviewSummary();
            
            this.renderAISuggestions();
        } catch (error) {
            console.error('Error loading AI suggestions:', error);
        }
    }
    
    renderAISuggestions() {
        const container = document.getElementById('ai-suggestions');
        if (!container) return;
        
        let html = '';
        
        // Add 5-minute overview summary at the top
        if (this.overviewSummary) {
            html += `
                <div class="col-span-full bg-gradient-to-r from-purple-900/50 to-blue-900/50 rounded-lg p-6 border border-purple-500/30 mb-6">
                    <div class="flex items-center gap-3 mb-3">
                        <span class="text-3xl">🧠</span>
                        <h3 class="text-xl font-semibold">5-Minute Overview</h3>
                    </div>
                    <div class="text-gray-200 space-y-2 text-sm">
                        ${this.overviewSummary}
                    </div>
                </div>
            `;
        }
        
        // Add personalized suggestion
        if (this.personalizedSuggestion) {
            html += `
                <div class="col-span-full bg-gradient-to-r from-green-900/50 to-teal-900/50 rounded-lg p-6 border border-green-500/30 mb-6">
                    <div class="flex items-center gap-3 mb-3">
                        <span class="text-3xl">✨</span>
                        <h3 class="text-xl font-semibold">Personalized for You</h3>
                    </div>
                    <div class="text-gray-200 space-y-2">
                        <p class="font-medium">${this.escapeHtml(this.personalizedSuggestion.title)}</p>
                        <p class="text-sm text-gray-300">${this.escapeHtml(this.personalizedSuggestion.description)}</p>
                        ${this.personalizedSuggestion.action ? `
                            <button onclick="dataLoader.handlePersonalizedAction('${this.personalizedSuggestion.action}')" 
                                    class="mt-2 bg-green-600 hover:bg-green-700 px-4 py-2 rounded text-sm">
                                ${this.personalizedSuggestion.actionLabel || 'Take Action'}
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        // Filter out dismissed suggestions
        const visibleSuggestions = this.aiSuggestions.filter(s => !this.dismissedSuggestions.has(s.id));
        
        if (visibleSuggestions.length === 0 && !this.overviewSummary && !this.personalizedSuggestion) {
            container.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">✅</div>
                    <h3 class="text-xl font-semibold mb-2">All Caught Up!</h3>
                    <p class="text-gray-400">No pending suggestions</p>
                </div>
            `;
            return;
        }
        
        html += visibleSuggestions.map(suggestion => {
            const feedback = this.feedbackData[`suggestion-${suggestion.id}`] || null;
            return `
            <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <div class="flex justify-between items-start mb-2">
                    <h4 class="font-semibold text-white">${this.escapeHtml(suggestion.title)}</h4>
                    ${suggestion.priority === 'high' ? '<span class="text-xs bg-red-600 px-2 py-1 rounded">High Priority</span>' : ''}
                </div>
                <p class="text-sm text-gray-400 mb-3 line-clamp-2">${this.escapeHtml(suggestion.description)}</p>
                <div class="flex gap-2 mb-2">
                    <button onclick="dataLoader.applySuggestion('${suggestion.id}')" 
                            class="flex-1 bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-sm">
                        ${suggestion.action === 'create_task' ? 'Create Task' : 'Review'}
                    </button>
                    <button onclick="dataLoader.dismissSuggestion('${suggestion.id}')" 
                            class="bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded text-sm">
                        Dismiss
                    </button>
                </div>
                <div class="flex gap-1 pt-2 border-t border-gray-700">
                    <button onclick="dataLoader.giveFeedback('suggestion', '${suggestion.id}', 'up')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                            title="Good suggestion">👍</button>
                    <button onclick="dataLoader.giveFeedback('suggestion', '${suggestion.id}', 'neutral')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                            title="Neutral">👌</button>
                    <button onclick="dataLoader.giveFeedback('suggestion', '${suggestion.id}', 'down')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                            title="Not helpful">👎</button>
                </div>
            </div>
        `;
        }).join('');
        
        container.innerHTML = html;
    }
    
    applySuggestion(id) {
        const suggestion = this.aiSuggestions.find(s => s.id === id);
        if (!suggestion) return;
        
        if (suggestion.action === 'create_task') {
            // Navigate to email or create task
            showSection('emails');
            if (suggestion.email_id) {
                this.showEmailDetail(suggestion.email_id);
            }
        } else {
            // Navigate to the relevant section
            showSection('emails');
            if (suggestion.email_id) {
                this.showEmailDetail(suggestion.email_id);
            }
        }
    }
    
    dismissSuggestion(id) {
        this.dismissedSuggestions.add(id);
        this.saveDismissedSuggestions();
        this.aiSuggestions = this.aiSuggestions.filter(s => s.id !== id);
        this.renderAISuggestions();
    }
    
    saveDismissedSuggestions() {
        localStorage.setItem('dismissedSuggestions', JSON.stringify([...this.dismissedSuggestions]));
    }
    
    loadDismissedSuggestions() {
        const stored = localStorage.getItem('dismissedSuggestions');
        if (stored) {
            this.dismissedSuggestions = new Set(JSON.parse(stored));
        }
    }
    
    async sendAIMessage() {
        const input = document.getElementById('ai-chat-input');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Add user message
        this.aiMessages.push({ role: 'user', content: message });
        this.renderAIChat();
        input.value = '';
        
        // IMMEDIATELY show "working" status
        const statusMessageId = `status_${Date.now()}`;
        this.aiMessages.push({
            role: 'status',
            content: '🤖 I\'m on it...',
            id: statusMessageId
        });
        this.renderAIChat();
        
        // Speak immediate acknowledgment if voice enabled
        if (this.aiVoiceEnabled && this.speechSynthesis) {
            this.speakText("I'm on it");
        }
        
        try {
            // Build comprehensive context with actual data
            const context = {
                current_time: new Date().toLocaleString(),
                todos: {
                    count: this.todos.length,
                    active_count: this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted').length,
                    items: this.todos.slice(0, 10).map(t => ({
                        title: t.title,
                        priority: t.priority,
                        due_date: t.due_date,
                        source: t.source,
                        status: t.status,
                        description: t.description ? t.description.substring(0, 100) : null
                    }))
                },
                calendar: {
                    count: this.calendar.length,
                    upcoming: this.calendar
                        .filter(e => new Date(e.start) > new Date())
                        .slice(0, 5)
                        .map(e => ({
                            summary: e.summary,
                            start: e.start,
                            location: e.location,
                            description: e.description ? e.description.substring(0, 100) : null
                        }))
                },
                emails: {
                    count: this.emails.length,
                    high_priority_count: this.emails.filter(e => e.priority === 'high').length,
                    recent: this.emails.slice(0, 5).map(e => ({
                        subject: e.subject,
                        sender: e.sender,
                        priority: e.priority,
                        has_todos: e.has_todos,
                        snippet: e.snippet ? e.snippet.substring(0, 100) : null
                    }))
                },
                user_preferences: {
                    liked_items_count: Object.keys(this.feedbackData).filter(
                        k => this.feedbackData[k] === 'like'
                    ).length,
                    recent_feedback: Object.entries(this.feedbackData)
                        .slice(-5)
                        .map(([key, value]) => ({ item: key, sentiment: value }))
                }
            };
            
            // Use EventSource for streaming responses with real-time progress updates
            const messageId = `msg_${Date.now()}`;
            // Reuse the statusMessageId we already created above
            let accumulatedResponse = '';
            let hasSeenResponse = false;
            
            // Build URL with query parameters for GET-compatible EventSource
            // Note: EventSource only supports GET, so we can't send large context in body
            // The backend will build context server-side
            const params = new URLSearchParams({
                message: message,
                conversation_id: this.conversationId || ''
            });
            
            const streamUrl = `/api/ai/chat/stream?${params.toString()}`;
            console.log('🚀 Opening AI stream:', streamUrl);
            
            const eventSource = new EventSource(streamUrl);
            
            eventSource.onopen = () => {
                console.log('✅ EventSource connection opened');
            };
            
            eventSource.onmessage = (event) => {
                console.log('📨 Received event:', event.data);
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'status') {
                        console.log('📊 Status update:', data.message);
                        // Show/update status message
                        const existingStatusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                        if (existingStatusIndex >= 0) {
                            this.aiMessages[existingStatusIndex].content = data.message;
                        } else {
                            this.aiMessages.push({
                                role: 'status',
                                content: data.message,
                                id: statusMessageId
                            });
                        }
                        this.renderAIChat();
                        
                    } else if (data.type === 'response') {
                        // Accumulate response chunks
                        accumulatedResponse += data.content;
                        
                        // Remove status message if present
                        if (!hasSeenResponse) {
                            const statusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                            if (statusIndex >= 0) {
                                this.aiMessages.splice(statusIndex, 1);
                            }
                            hasSeenResponse = true;
                        }
                        
                        // Update or create response message
                        const existingIndex = this.aiMessages.findIndex(m => m.id === messageId);
                        if (existingIndex >= 0) {
                            this.aiMessages[existingIndex].content = accumulatedResponse;
                        } else {
                            this.aiMessages.push({
                                role: 'assistant',
                                content: accumulatedResponse,
                                id: messageId,
                                conversation_id: this.conversationId
                            });
                        }
                        this.renderAIChat();
                        
                    } else if (data.type === 'done') {
                        // Save conversation ID
                        if (data.conversation_id) {
                            this.conversationId = data.conversation_id;
                            
                            // Update conversation_id on the message
                            const msgIndex = this.aiMessages.findIndex(m => m.id === messageId);
                            if (msgIndex >= 0) {
                                this.aiMessages[msgIndex].conversation_id = data.conversation_id;
                            }
                        }
                        
                        // Speak the complete response if voice is enabled
                        if (this.aiVoiceEnabled && this.speechSynthesis && accumulatedResponse) {
                            this.speakText(accumulatedResponse);
                        }
                        
                        eventSource.close();
                        
                    } else if (data.type === 'error') {
                        // Remove status message if present
                        const statusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                        if (statusIndex >= 0) {
                            this.aiMessages.splice(statusIndex, 1);
                        }
                        
                        const errorMsg = data.message || 'Sorry, I encountered an error. Please try again.';
                        this.aiMessages.push({ 
                            role: 'assistant', 
                            content: errorMsg,
                            id: messageId
                        });
                        this.renderAIChat();
                        
                        if (this.aiVoiceEnabled && this.speechSynthesis) {
                            this.speakText(errorMsg);
                        }
                        
                        eventSource.close();
                    }
                } catch (parseError) {
                    console.error('Error parsing event data:', parseError, event.data);
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('❌ EventSource error:', error);
                console.error('EventSource readyState:', eventSource.readyState);
                eventSource.close();
                
                // Remove status message if present
                const statusIndex = this.aiMessages.findIndex(m => m.id === statusMessageId);
                if (statusIndex >= 0) {
                    this.aiMessages.splice(statusIndex, 1);
                }
                
                // Only show error if no response was received
                if (!hasSeenResponse) {
                    const errorMsg = 'Sorry, I encountered an error. Please try again.';
                    this.aiMessages.push({ 
                        role: 'assistant', 
                        content: errorMsg,
                        id: messageId
                    });
                    this.renderAIChat();
                    
                    if (this.aiVoiceEnabled && this.speechSynthesis) {
                        this.speakText(errorMsg);
                    }
                }
            };
        } catch (error) {
            console.error('Error sending AI message:', error);
            const errorMsg = 'Sorry, I encountered an error. Please try again.';
            this.aiMessages.push({ 
                role: 'assistant', 
                content: errorMsg
            });
            this.renderAIChat();
            
            if (this.aiVoiceEnabled && this.speechSynthesis) {
                this.speakText(errorMsg);
            }
        }
    }
    
    speakText(text) {
        if (!this.speechSynthesis) return;
        
        // Check if globally muted
        if (this.globalMuted) {
            console.log('🔇 Voice muted globally');
            return;
        }
        
        // Cancel any ongoing speech
        this.speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        utterance.volume = 0.8;
        
        // Get available voices (they may have loaded since init)
        const voices = this.speechSynthesis.getVoices();
        
        // If voices just loaded, update our list
        if (voices.length > this.availableVoices.length) {
            this.availableVoices = voices;
            console.log('🔄 Voices updated, now have', voices.length, 'voices');
        }
        
        // If we have a selected voice, use it
        if (this.selectedVoice) {
            const voice = voices.find(v => v.name === this.selectedVoice);
            if (voice) {
                utterance.voice = voice;
                console.log('🎤 Using voice:', voice.name);
            } else {
                console.warn('⚠️ Selected voice not found:', this.selectedVoice);
                // Try to set a new default
                this.setDefaultVoice();
            }
        } else if (voices.length > 0) {
            // No voice selected yet, set default
            this.setDefaultVoice();
            if (this.selectedVoice) {
                const voice = voices.find(v => v.name === this.selectedVoice);
                if (voice) {
                    utterance.voice = voice;
                    console.log('🎤 Using default voice:', voice.name);
                }
            }
        }
        
        // Show stop button and start listening for stop commands
        this.showStopSpeechButton();
        this.startStopCommandListener();
        
        // Hide stop button and stop listener when speech ends
        utterance.onend = () => {
            this.hideStopSpeechButton();
            this.stopStopCommandListener();
        };
        
        utterance.onerror = (error) => {
            console.error('Speech error:', error);
            this.hideStopSpeechButton();
            this.stopStopCommandListener();
        };
        
        this.speechSynthesis.speak(utterance);
    }
    
    stopSpeech() {
        if (this.speechSynthesis) {
            this.speechSynthesis.cancel();
            this.hideStopSpeechButton();
            this.stopStopCommandListener();
        }
    }
    
    showStopSpeechButton() {
        let stopBtn = document.getElementById('stop-speech-btn');
        if (!stopBtn) {
            stopBtn = document.createElement('button');
            stopBtn.id = 'stop-speech-btn';
            stopBtn.className = 'fixed bottom-8 right-8 z-50 bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-full shadow-lg flex items-center gap-2 animate-pulse';
            stopBtn.innerHTML = `
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path>
                </svg>
                <span class="font-semibold">Stop Speaking</span>
            `;
            stopBtn.onclick = () => this.stopSpeech();
            document.body.appendChild(stopBtn);
        }
        stopBtn.style.display = 'flex';
    }
    
    hideStopSpeechButton() {
        const stopBtn = document.getElementById('stop-speech-btn');
        if (stopBtn) {
            stopBtn.style.display = 'none';
        }
    }
    
    renderAIChat() {
        const container = document.getElementById('ai-chat-messages');
        if (!container) return;
        
        if (this.aiMessages.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <p>Start a conversation with your AI assistant</p>
                    <p class="text-xs mt-2">Powered by ${this.userProfile?.preferred_name ? this.userProfile.preferred_name + "'s" : 'your'} personalized profile</p>
                </div>
            `;
            return;
        }
        
        const html = this.aiMessages.map((msg, index) => {
            if (msg.role === 'user') {
                return `
                    <div class="text-right">
                        <div class="inline-block max-w-[80%] bg-blue-600 rounded-lg px-4 py-2">
                            <p class="text-sm">${this.escapeHtml(msg.content)}</p>
                        </div>
                    </div>
                `;
            } else if (msg.role === 'status') {
                // Status messages: small, gray, italic with emoji
                return `
                    <div class="text-left">
                        <div class="inline-block max-w-[80%] bg-gray-800/50 rounded-lg px-3 py-1.5 border border-gray-700/50">
                            <p class="text-xs text-gray-400 italic">${this.escapeHtml(msg.content)}</p>
                        </div>
                    </div>
                `;
            } else {
                return `
                    <div class="text-left">
                        <div class="inline-block max-w-[80%] bg-gray-700 rounded-lg px-4 py-2">
                            <p class="text-sm">${this.escapeHtml(msg.content)}</p>
                            ${msg.id ? `
                                <div class="flex gap-2 mt-2 pt-2 border-t border-gray-600">
                                    <button onclick="dataLoader.rateAIMessage('${msg.id}', '${msg.conversation_id}', 'thumbs_up')" 
                                            class="text-xs px-2 py-1 bg-gray-600 hover:bg-green-600 rounded">
                                        👍 Helpful
                                    </button>
                                    <button onclick="dataLoader.rateAIMessage('${msg.id}', '${msg.conversation_id}', 'thumbs_down')" 
                                            class="text-xs px-2 py-1 bg-gray-600 hover:bg-red-600 rounded">
                                        👎 Not Helpful
                                    </button>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }
        }).join('');
        
        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    }
    
    async rateAIMessage(messageId, conversationId, feedbackType) {
        try {
            const response = await fetch('/api/ai/message/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message_id: messageId,
                    conversation_id: conversationId,
                    feedback_type: feedbackType
                })
            });
            
            if (response.ok) {
                this.showNotification(`Feedback recorded: ${feedbackType === 'thumbs_up' ? '👍 Helpful' : '👎 Not Helpful'}`, 'success');
            }
        } catch (error) {
            console.error('Error rating message:', error);
        }
    }
    
    async loadUserProfile() {
        try {
            const response = await fetch('/api/user/profile');
            if (response.ok) {
                this.userProfile = await response.json();
                console.log('User profile loaded:', this.userProfile);
            }
        } catch (error) {
            console.error('Error loading user profile:', error);
        }
    }
    
    async saveUserProfile(profile) {
        try {
            const response = await fetch('/api/user/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(profile)
            });
            
            if (response.ok) {
                this.userProfile = profile;
                this.showNotification('Profile saved successfully!', 'success');
            }
        } catch (error) {
            console.error('Error saving user profile:', error);
            this.showNotification('Failed to save profile', 'error');
        }
    }
    
    showUserProfileModal() {
        const profile = this.userProfile || {};
        
        const modal = document.createElement('div');
        modal.id = 'user-profile-modal';
        modal.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 modal-backdrop';
        modal.innerHTML = `
            <div class="bg-gray-800 rounded-xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto modal-content">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold">Your AI Profile</h2>
                    <button onclick="document.getElementById('user-profile-modal').remove()" 
                            class="text-gray-400 hover:text-white text-2xl">&times;</button>
                </div>
                
                <p class="text-sm text-gray-400 mb-6">
                    Help the AI assistant understand you better by providing context about yourself, 
                    your work, and preferences. This information will be used to personalize responses.
                </p>
                
                <form id="profile-form" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Full Name</label>
                        <input type="text" name="full_name" value="${profile.full_name || ''}" 
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Preferred Name</label>
                        <input type="text" name="preferred_name" value="${profile.preferred_name || ''}" 
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium mb-2">Role/Title</label>
                            <input type="text" name="role" value="${profile.role || ''}" 
                                   class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                        </div>
                        <div>
                            <label class="block text-sm font-medium mb-2">Company</label>
                            <input type="text" name="company" value="${profile.company || ''}" 
                                   class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Work Focus</label>
                        <input type="text" name="work_focus" value="${profile.work_focus || ''}" 
                               placeholder="e.g., Software Development, Marketing, Product Management"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Interests</label>
                        <input type="text" name="interests" value="${profile.interests || ''}" 
                               placeholder="e.g., AI, Music, Technology, Sports"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Communication Style</label>
                        <select name="communication_style" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                            <option value="Professional and formal" ${profile.communication_style === 'Professional and formal' ? 'selected' : ''}>Professional and formal</option>
                            <option value="Professional and friendly" ${!profile.communication_style || profile.communication_style === 'Professional and friendly' ? 'selected' : ''}>Professional and friendly</option>
                            <option value="Casual and conversational" ${profile.communication_style === 'Casual and conversational' ? 'selected' : ''}>Casual and conversational</option>
                            <option value="Direct and concise" ${profile.communication_style === 'Direct and concise' ? 'selected' : ''}>Direct and concise</option>
                        </select>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Work Hours</label>
                        <input type="text" name="work_hours" value="${profile.work_hours || ''}" 
                               placeholder="e.g., 9am-5pm EST, Flexible"
                               class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Current Priorities</label>
                        <textarea name="priorities" rows="3" 
                                  placeholder="What are you focusing on right now?"
                                  class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">${profile.priorities || ''}</textarea>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Bio / Context</label>
                        <textarea name="bio" rows="4" 
                                  placeholder="Anything else the AI should know about you?"
                                  class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">${profile.bio || ''}</textarea>
                    </div>
                    
                    <div class="flex gap-3 pt-4">
                        <button type="submit" 
                                class="flex-1 bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-semibold">
                            Save Profile
                        </button>
                        <button type="button" 
                                onclick="document.getElementById('user-profile-modal').remove()"
                                class="bg-gray-600 hover:bg-gray-700 px-6 py-3 rounded-lg">
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Handle form submission
        document.getElementById('profile-form').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const profile = Object.fromEntries(formData.entries());
            await this.saveUserProfile(profile);
            modal.remove();
        };
    }
    
    toggleAIVoice() {
        this.aiVoiceEnabled = !this.aiVoiceEnabled;
        
        // Persist the setting
        localStorage.setItem('aiVoiceEnabled', this.aiVoiceEnabled);
        
        // Stop any currently speaking text
        if (!this.aiVoiceEnabled && this.speechSynthesis && this.speechSynthesis.speaking) {
            this.speechSynthesis.cancel();
        }
        
        const btn = document.getElementById('ai-voice-toggle');
        if (btn) {
            btn.textContent = this.aiVoiceEnabled ? '🔊 Voice On' : '🔇 Voice Off';
            btn.className = this.aiVoiceEnabled ? 
                'bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-sm' : 
                'bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm';
        }
        
        // Show notification
        this.showNotification(
            this.aiVoiceEnabled ? 'Voice responses enabled' : 'Voice responses muted',
            'info'
        );
    }
    
    toggleGlobalMute() {
        this.globalMuted = !this.globalMuted;
        
        // Persist the setting
        localStorage.setItem('globalMuted', this.globalMuted);
        
        // Stop any currently speaking text
        if (this.globalMuted && this.speechSynthesis && this.speechSynthesis.speaking) {
            this.speechSynthesis.cancel();
            this.hideStopSpeechButton();
        }
        
        // Update button UI
        const iconEl = document.getElementById('mute-icon');
        const textEl = document.getElementById('mute-text');
        const btnEl = document.getElementById('global-mute-btn');
        
        if (iconEl && textEl && btnEl) {
            if (this.globalMuted) {
                iconEl.textContent = '🔇';
                textEl.textContent = 'Voice Alerts Off';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            } else {
                iconEl.textContent = '🔊';
                textEl.textContent = 'Voice Alerts On';
                btnEl.className = 'mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg';
            }
        }
        
        // Show notification
        this.showNotification(
            this.globalMuted ? '🔇 All voice alerts muted' : '🔊 Voice alerts enabled',
            'info'
        );
    }
    
    startVoicePrompt() {
        if (!this.voiceRecognition) {
            alert('Voice recognition is not supported in your browser.');
            return;
        }
        
        const btn = document.getElementById('ai-voice-prompt');
        if (btn) {
            btn.textContent = '🎤 Listening...';
            btn.classList.add('animate-pulse');
        }
        
        this.voiceRecognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            const input = document.getElementById('ai-chat-input');
            if (input) {
                input.value = transcript;
                this.sendAIMessage();
            }
            
            if (btn) {
                btn.textContent = '🎤 Voice Prompt';
                btn.classList.remove('animate-pulse');
            }
        };
        
        this.voiceRecognition.onerror = (event) => {
            console.error('Voice recognition error:', event.error);
            if (btn) {
                btn.textContent = '🎤 Voice Prompt';
                btn.classList.remove('animate-pulse');
            }
        };
        
        this.voiceRecognition.start();
    }
    
    // VANITY ALERTS
    async loadVanityAlerts() {
        try {
            const response = await fetch('/api/vanity-alerts');
            if (response.ok) {
                const data = await response.json();
                this.vanityAlerts = data.alerts || [];
                this.renderVanityAlerts();
            }
        } catch (error) {
            console.error('Error loading vanity alerts:', error);
        }
    }
    
    renderVanityAlerts() {
        const grid = document.getElementById('vanity-grid');
        if (!grid) return;
        
        if (this.vanityAlerts.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🔔</div>
                    <h3 class="text-xl font-semibold mb-2">No Alerts</h3>
                    <p class="text-gray-400">No brand mentions or alerts found</p>
                </div>
            `;
            return;
        }
        
        const html = this.vanityAlerts.map(alert => {
            const feedback = this.feedbackData[`vanity-${alert.id}`] || null;
            return `
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700 relative">
                <button onclick="dismissAlert('${alert.id}')" 
                        class="absolute top-2 right-2 text-gray-400 hover:text-white px-2 py-1 rounded hover:bg-gray-700" 
                        title="Dismiss">✕</button>
                <div class="flex items-start gap-3 mb-3">
                    <span class="text-3xl">${this.getAlertIcon(alert.type)}</span>
                    <div class="flex-1">
                        <h3 class="font-semibold text-white mb-1">${this.escapeHtml(alert.title)}</h3>
                        <p class="text-sm text-gray-400 mb-2">${this.escapeHtml(alert.description || '')}</p>
                        <div class="flex gap-2 text-xs">
                            ${alert.source ? `<span class="bg-purple-600 px-2 py-1 rounded">${this.escapeHtml(alert.source)}</span>` : ''}
                            ${alert.url ? `<a href="${alert.url}" target="_blank" class="text-blue-400 hover:underline">View →</a>` : ''}
                        </div>
                    </div>
                </div>
                <div class="flex gap-1 pt-3 border-t border-gray-700">
                    <button onclick="dataLoader.giveFeedback('vanity', '${alert.id}', 'up')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'up' ? 'bg-green-600' : 'bg-gray-700 hover:bg-green-600'}" 
                            title="Important">👍</button>
                    <button onclick="dataLoader.giveFeedback('vanity', '${alert.id}', 'neutral')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'neutral' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-blue-600'}" 
                            title="Neutral">👌</button>
                    <button onclick="dataLoader.giveFeedback('vanity', '${alert.id}', 'down')" 
                            class="feedback-btn px-2 py-1 rounded text-xs ${feedback === 'down' ? 'bg-red-600' : 'bg-gray-700 hover:bg-red-600'}" 
                            title="Not relevant">👎</button>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = html;
    }
    
    getAlertIcon(type) {
        const icons = {
            'mention': '💬',
            'social': '📱',
            'web': '🌐',
            'press': '📰',
            'review': '⭐',
            'default': '🔔'
        };
        return icons[type] || icons.default;
    }
    
    getItemTypeIcon(type) {
        const icons = {
            'todo': '✅',
            'Task': '✅',
            'event': '📅',
            'Event': '📅',
            'email': '📧',
            'Email': '📧',
            'news': '📰',
            'News': '📰',
            'suggestion': '💡',
            'vanity': '🔔',
            'music': '🎵',
            'default': '⭐'
        };
        return icons[type] || icons.default;
    }
    
    // LIKED ITEMS
    async loadLikedItems() {
        try {
            const response = await fetch('/api/liked-items');
            if (response.ok) {
                const data = await response.json();
                this.renderLikedItemsFromDB(data.liked_items || []);
                return;
            }
        } catch (error) {
            console.error('Error loading liked items from database:', error);
        }
        
        // Fallback to localStorage if API fails
        this.renderLikedItemsFromStorage();
    }
    
    renderLikedItemsFromDB(likedItems) {
        const grid = document.getElementById('liked-grid');
        if (!grid) return;
        
        if (likedItems.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">❤️</div>
                    <h3 class="text-xl font-semibold mb-2">No Liked Items</h3>
                    <p class="text-gray-400">Start giving thumbs up to items you like!</p>
                </div>
            `;
            return;
        }
        
        const html = likedItems.map(item => `
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <div class="flex items-start gap-3">
                    <span class="text-3xl">${this.getItemTypeIcon(item.item_type)}</span>
                    <div class="flex-1">
                        <span class="text-xs text-purple-400 mb-1 block">${item.item_type}</span>
                        <h3 class="font-semibold text-white mb-1">${this.escapeHtml(item.title || item.item_details?.title || 'Liked Item')}</h3>
                        ${item.description || item.item_details?.description ? `<p class="text-sm text-gray-400">${this.escapeHtml(item.description || item.item_details?.description)}</p>` : ''}
                        <p class="text-xs text-gray-500 mt-2">${this.formatDate(item.created_at)}</p>
                    </div>
                </div>
            </div>
        `).join('');
        
        grid.innerHTML = html;
    }
    
    renderLikedItemsFromStorage() {
        const grid = document.getElementById('liked-grid');
        if (!grid) return;
        
        const likedItems = [];
        
        // Collect all items marked with thumbs up
        Object.entries(this.feedbackData).forEach(([key, sentiment]) => {
            if (sentiment === 'up') {
                const [type, id] = key.split('-');
                let item = null;
                
                switch(type) {
                    case 'todo':
                        item = this.todos.find(t => t.id === id);
                        if (item) likedItems.push({ type: 'Task', icon: '✅', title: item.title, description: item.description, id: key });
                        break;
                    case 'event':
                        item = this.calendar.find(e => e.event_id === id);
                        if (item) likedItems.push({ type: 'Event', icon: '📅', title: item.summary || item.title, description: item.location, id: key });
                        break;
                    case 'email':
                        item = this.emails.find(e => e.id === id);
                        if (item) likedItems.push({ type: 'Email', icon: '📧', title: item.subject, description: item.sender, id: key });
                        break;
                    case 'news':
                        item = this.news.find(n => n.id === id);
                        if (item) likedItems.push({ type: 'News', icon: '📰', title: item.title, description: item.source, id: key });
                        break;
                }
            }
        });
        
        if (likedItems.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">❤️</div>
                    <h3 class="text-xl font-semibold mb-2">No Liked Items</h3>
                    <p class="text-gray-400">Start giving thumbs up to items you like!</p>
                </div>
            `;
            return;
        }
        
        const html = likedItems.map(item => `
            <div class="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <div class="flex items-start gap-3">
                    <span class="text-3xl">${item.icon}</span>
                    <div class="flex-1">
                        <span class="text-xs text-purple-400 mb-1 block">${item.type}</span>
                        <h3 class="font-semibold text-white mb-1">${this.escapeHtml(item.title)}</h3>
                        ${item.description ? `<p class="text-sm text-gray-400">${this.escapeHtml(item.description)}</p>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
        
        grid.innerHTML = html;
    }
    
    // MUSIC NEWS
    async loadMusicNews() {
        try {
            const response = await fetch('/api/music');
            if (response.ok) {
                const data = await response.json();
                // Combine all music-related data into one array
                const allMusic = [];
                
                // Add streaming stats/tracks
                if (data.tracks && data.tracks.length > 0) {
                    allMusic.push(...data.tracks.map(track => ({
                        id: `track-${track.platform}-${Date.now()}`,
                        title: track.title,
                        artist: track.artist,
                        description: track.trending_tracks ? `Trending: ${track.trending_tracks.slice(0, 3).join(', ')}` : '',
                        type: 'streaming',
                        platform: track.platform,
                        plays: track.plays,
                        followers: track.followers
                    })));
                }
                
                // Add music news articles
                if (data.music_news && data.music_news.length > 0) {
                    allMusic.push(...data.music_news.map(article => ({
                        id: `news-${article.url}`,
                        title: article.title,
                        artist: article.source,
                        description: article.snippet,
                        type: 'news',
                        url: article.url,
                        release_date: article.published_date
                    })));
                }
                
                // Add label mentions
                if (data.label_mentions && data.label_mentions.length > 0) {
                    allMusic.push(...data.label_mentions.slice(0, 5).map(mention => ({
                        id: `label-${mention.url}`,
                        title: `Null Records mentioned on ${mention.platform}`,
                        artist: mention.source || mention.platform,
                        description: mention.text,
                        type: 'mention',
                        url: mention.url,
                        engagement: mention.engagement,
                        release_date: mention.date
                    })));
                }
                
                // Add band mentions
                if (data.band_mentions && data.band_mentions.length > 0) {
                    allMusic.push(...data.band_mentions.slice(0, 5).map(mention => ({
                        id: `band-${mention.url}`,
                        title: `Artist mentioned on ${mention.platform}`,
                        artist: mention.source || mention.platform,
                        description: mention.text,
                        type: 'mention',
                        url: mention.url,
                        engagement: mention.engagement,
                        release_date: mention.date
                    })));
                }
                
                this.musicNews = allMusic;
                this.renderMusicNews();
                
                // Load music player data
                this.loadUnifiedLibrary();
                this.loadPlaylists();
            }
        } catch (error) {
            console.error('Error loading music news:', error);
        }
    }
    
    renderMusicNews() {
        const grid = document.getElementById('music-grid');
        if (!grid) return;
        
        if (this.musicNews.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🎵</div>
                    <h3 class="text-xl font-semibold mb-2">No Music News</h3>
                    <p class="text-gray-400">No music updates available</p>
                </div>
            `;
            return;
        }
        
        const html = this.musicNews.map(music => {
            const feedback = this.feedbackData[`music-${music.id}`] || null;
            const typeEmoji = {
                'streaming': '📊',
                'news': '📰',
                'mention': '💬',
                'release': '🎵'
            };
            
            return `
            <div class="bg-gray-750 rounded-lg p-4 border border-gray-600 ${music.url ? 'cursor-pointer hover:border-purple-500 transition-colors' : ''}"
                 ${music.url ? `onclick="window.open('${music.url}', '_blank')"` : ''}>
                <div class="flex items-start gap-3">
                    <span class="text-2xl">${typeEmoji[music.type] || '🎵'}</span>
                    <div class="flex-1 min-w-0">
                        <h4 class="font-semibold text-white text-sm mb-1 truncate">${this.escapeHtml(music.title)}</h4>
                        <p class="text-xs text-purple-400 mb-1">${this.escapeHtml(music.artist || '')}</p>
                        ${music.description ? `<p class="text-xs text-gray-400 line-clamp-2">${this.escapeHtml(music.description)}</p>` : ''}
                        <div class="flex gap-1 text-xs mt-2 flex-wrap">
                            ${music.type ? `<span class="bg-purple-600 px-2 py-0.5 rounded text-xs">${this.escapeHtml(music.type)}</span>` : ''}
                            ${music.platform ? `<span class="bg-blue-600 px-2 py-0.5 rounded text-xs">${this.escapeHtml(music.platform)}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        }).join('');
        
        grid.innerHTML = html;
    }
    
    // UNIVERSAL MUSIC PLAYER FUNCTIONS
    async connectService(service) {
        this.showNotification(`Connecting to ${service}...`, 'info');
        try {
            if (service === 'spotify') {
                // Redirect to Spotify OAuth
                window.location.href = '/api/music/oauth/spotify/login';
            } else if (service === 'apple') {
                // Initialize MusicKit JS for Apple Music
                await this.connectAppleMusic();
            } else if (service === 'amazon') {
                this.showNotification('Amazon Music integration coming soon!', 'info');
            }
        } catch (error) {
            console.error(`Error connecting to ${service}:`, error);
            this.showNotification(`Failed to connect to ${service}`, 'error');
        }
    }
    
    async connectAppleMusic() {
        try {
            // Get Apple Music configuration
            const response = await fetch('/api/music/oauth/apple/login');
            if (!response.ok) {
                throw new Error('Failed to get Apple Music configuration');
            }
            
            const config = await response.json();
            
            // Load MusicKit JS if not already loaded
            if (!window.MusicKit) {
                await this.loadMusicKitJS();
            }
            
            // Configure MusicKit
            await MusicKit.configure(config.music_kit_config);
            
            // Get the MusicKit instance
            const music = MusicKit.getInstance();
            
            // Authorize the user
            const userToken = await music.authorize();
            
            // Save the user token to backend
            const saveResponse = await fetch('/api/music/oauth/apple/callback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_token: userToken })
            });
            
            if (saveResponse.ok) {
                this.showNotification('Apple Music connected successfully!', 'success');
                this.updateServiceStatus('apple', true);
            } else {
                throw new Error('Failed to save Apple Music token');
            }
        } catch (error) {
            console.error('Error connecting Apple Music:', error);
            this.showNotification('Failed to connect Apple Music', 'error');
        }
    }
    
    loadMusicKitJS() {
        return new Promise((resolve, reject) => {
            if (document.getElementById('musickit-js')) {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.id = 'musickit-js';
            script.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    
    updateServiceStatus(service, connected) {
        const statusSpan = document.querySelector(`.${service}-status`);
        if (statusSpan) {
            statusSpan.textContent = connected ? 'Connected' : 'Not Connected';
            statusSpan.parentElement.style.color = connected ? '#10b981' : '#ef4444';
        }
    }
    
    async loadUnifiedLibrary() {
        try {
            const response = await fetch('/api/music/unified-library');
            if (response.ok) {
                const data = await response.json();
                this.renderUnifiedLibrary(data.tracks || []);
            }
        } catch (error) {
            console.error('Error loading unified library:', error);
        }
    }
    
    renderUnifiedLibrary(tracks) {
        const container = document.getElementById('unified-library');
        if (!container) return;
        
        if (tracks.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No tracks found. Connect your music services first.</p>';
            return;
        }
        
        const html = tracks.slice(0, 20).map(track => `
            <div class="flex items-center gap-3 p-2 bg-gray-750 rounded hover:bg-gray-700 cursor-pointer transition"
                 onclick="dataLoader.playTrack('${track.id}', '${track.service}')">
                <span class="text-xl">🎵</span>
                <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium truncate">${this.escapeHtml(track.title)}</div>
                    <div class="text-xs text-gray-400 truncate">${this.escapeHtml(track.artist)}</div>
                </div>
                <span class="service-badge text-xs px-2 py-1 bg-gray-600 rounded">${track.service}</span>
            </div>
        `).join('');
        
        container.innerHTML = html;
    }
    
    async createMoodPlaylist() {
        const mood = document.getElementById('mood-selector')?.value;
        const maxTracks = document.getElementById('mood-max-tracks')?.value || 30;
        const useAI = document.getElementById('use-ai-mood')?.checked || false;
        
        if (!mood) {
            this.showNotification('Please select a mood', 'error');
            return;
        }
        
        this.showNotification(`Creating ${mood} playlist...`, 'info');
        
        try {
            const response = await fetch('/api/music/create-mood-playlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mood, max_tracks: parseInt(maxTracks), use_ai: useAI })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showNotification(`Created ${mood} playlist with ${data.tracks.length} tracks!`, 'success');
                this.loadPlaylists();
            }
        } catch (error) {
            console.error('Error creating mood playlist:', error);
            this.showNotification('Failed to create playlist', 'error');
        }
    }
    
    async createCustomPlaylist() {
        const genres = document.getElementById('custom-genres')?.value.split(',').map(g => g.trim()).filter(g => g);
        const artists = document.getElementById('custom-artists')?.value.split(',').map(a => a.trim()).filter(a => a);
        const minPop = parseInt(document.getElementById('custom-min-pop')?.value || 0);
        const maxPop = parseInt(document.getElementById('custom-max-pop')?.value || 100);
        
        if (!genres.length && !artists.length) {
            this.showNotification('Please specify at least one genre or artist', 'error');
            return;
        }
        
        this.showNotification('Creating custom playlist...', 'info');
        
        try {
            const response = await fetch('/api/music/create-custom-playlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    criteria: {
                        genres: genres,
                        artists: artists,
                        min_popularity: minPop,
                        max_popularity: maxPop
                    }
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showNotification(`Created custom playlist with ${data.tracks.length} tracks!`, 'success');
                this.loadPlaylists();
            }
        } catch (error) {
            console.error('Error creating custom playlist:', error);
            this.showNotification('Failed to create playlist', 'error');
        }
    }
    
    async loadPlaylists() {
        try {
            const response = await fetch('/api/music/playlists');
            if (response.ok) {
                const data = await response.json();
                this.renderPlaylists(data.playlists || []);
            }
        } catch (error) {
            console.error('Error loading playlists:', error);
        }
    }
    
    renderPlaylists(playlists) {
        const grid = document.getElementById('playlists-grid');
        if (!grid) return;
        
        if (playlists.length === 0) {
            grid.innerHTML = '<p class="text-gray-400 col-span-full text-center">No playlists yet. Create one above!</p>';
            return;
        }
        
        const html = playlists.map(playlist => `
            <div class="bg-gray-750 rounded-lg p-4 border border-gray-600 hover:border-purple-500 transition cursor-pointer"
                 onclick="dataLoader.playPlaylist('${playlist.id}')">
                <div class="flex items-center gap-3 mb-3">
                    <span class="text-3xl">🎵</span>
                    <div class="flex-1 min-w-0">
                        <h4 class="font-semibold truncate">${this.escapeHtml(playlist.name)}</h4>
                        <p class="text-xs text-gray-400">${playlist.tracks.length} tracks</p>
                    </div>
                </div>
                <div class="flex gap-2 text-xs">
                    ${playlist.mood ? `<span class="bg-purple-600 px-2 py-1 rounded">${playlist.mood}</span>` : ''}
                    ${playlist.created_at ? `<span class="bg-gray-700 px-2 py-1 rounded">${this.formatDate(playlist.created_at)}</span>` : ''}
                </div>
            </div>
        `).join('');
        
        grid.innerHTML = html;
    }
    
    // Playback Controls (stubs for now - need actual player integration)
    playTrack(trackId, service) {
        const title = document.getElementById('now-playing-title');
        const artist = document.getElementById('now-playing-artist');
        const serviceBadge = document.getElementById('playing-service');
        
        if (title) title.textContent = `Playing track ${trackId}`;
        if (artist) artist.textContent = `from ${service}`;
        if (serviceBadge) {
            serviceBadge.textContent = service.toUpperCase();
            serviceBadge.className = 'service-badge bg-blue-600 px-2 py-1 rounded text-xs';
            serviceBadge.classList.remove('hidden');
        }
        
        const btn = document.getElementById('play-pause-btn');
        if (btn) btn.textContent = '⏸️';
        
        this.showNotification(`Playing track from ${service}`, 'info');
    }
    
    playPlaylist(playlistId) {
        this.showNotification(`Starting playlist ${playlistId}`, 'info');
    }
    
    togglePlay() {
        const btn = document.getElementById('play-pause-btn');
        if (!btn) return;
        
        const isPlaying = btn.textContent === '⏸️';
        btn.textContent = isPlaying ? '▶️' : '⏸️';
        this.showNotification(isPlaying ? 'Paused' : 'Playing', 'info');
    }
    
    previousTrack() {
        this.showNotification('Previous track', 'info');
    }
    
    nextTrack() {
        this.showNotification('Next track', 'info');
    }
    
    setVolume(value) {
        const display = document.getElementById('volume-display');
        if (display) display.textContent = `${value}%`;
    }
    
    // DASHBOARD EDIT MODE
    toggleEditMode() {
        this.editMode = !this.editMode;
        const btn = document.getElementById('edit-mode-btn');
        
        if (this.editMode) {
            if (btn) {
                btn.innerHTML = '<span>✅</span><span>Save Settings</span>';
                btn.className = 'w-full bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg text-sm flex items-center justify-center gap-2 mb-2';
            }
            this.showEditPanel();
        } else {
            if (btn) {
                btn.innerHTML = '<span>⚙️</span><span>Edit Dashboard</span>';
                btn.className = 'w-full bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-sm flex items-center justify-center gap-2 mb-2';
            }
            this.hideEditPanel();
            this.saveDashboardConfig();
            this.updateNavVisibility();
        }
    }
    
    showEditPanel() {
        const panel = document.createElement('div');
        panel.id = 'edit-panel';
        panel.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto';
        panel.onclick = (e) => {
            if (e.target === panel) this.hideEditPanel();
        };
        
        panel.innerHTML = `
            <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 shadow-2xl max-w-2xl w-full my-8 max-h-[90vh] overflow-y-auto">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-xl font-bold">Configure Dashboard</h3>
                    <button onclick="dataLoader.hideEditPanel()" 
                            class="text-gray-400 hover:text-white text-2xl leading-none">
                        ×
                    </button>
                </div>
                
                <p class="text-sm text-gray-400 mb-4">Customize your dashboard sections and settings</p>
                
                <div class="space-y-6">
                    <div>
                        <h4 class="text-lg font-semibold mb-3">Dashboard Sections</h4>
                        <div class="grid grid-cols-2 gap-2">
                            ${Object.entries(this.dashboardConfig).map(([key, enabled]) => `
                                <label class="flex items-center gap-2 p-2 rounded hover:bg-gray-700 cursor-pointer">
                                    <input type="checkbox" 
                                           ${enabled ? 'checked' : ''} 
                                           onchange="dataLoader.toggleSection('${key}')"
                                           class="w-4 h-4 rounded">
                                    <span class="text-sm capitalize">${key}</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>
            
            <div class="border-t border-gray-700 pt-4 mb-4">
                <h4 class="text-lg font-semibold mb-3">Auto-Refresh Interval</h4>
                <p class="text-xs text-gray-400 mb-3">Automatically refresh data and generate overview prompts</p>
                <select onchange="dataLoader.setAutoRefreshInterval(this.value)" 
                        class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                    <option value="0" ${this.autoRefreshInterval === 0 ? 'selected' : ''}>Disabled</option>
                    <option value="5" ${this.autoRefreshInterval === 5 ? 'selected' : ''}>Every 5 minutes</option>
                    <option value="15" ${this.autoRefreshInterval === 15 ? 'selected' : ''}>Every 15 minutes</option>
                    <option value="30" ${this.autoRefreshInterval === 30 ? 'selected' : ''}>Every 30 minutes</option>
                    <option value="60" ${this.autoRefreshInterval === 60 ? 'selected' : ''}>Every hour</option>
                </select>
            </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">Auto-Refresh Interval</h4>
                        <p class="text-xs text-gray-400 mb-3">Automatically refresh data and generate overview prompts</p>
                        <select onchange="dataLoader.setAutoRefreshInterval(this.value)" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                            <option value="0" ${this.autoRefreshInterval === 0 ? 'selected' : ''}>Disabled</option>
                            <option value="5" ${this.autoRefreshInterval === 5 ? 'selected' : ''}>Every 5 minutes</option>
                            <option value="15" ${this.autoRefreshInterval === 15 ? 'selected' : ''}>Every 15 minutes</option>
                            <option value="30" ${this.autoRefreshInterval === 30 ? 'selected' : ''}>Every 30 minutes</option>
                            <option value="60" ${this.autoRefreshInterval === 60 ? 'selected' : ''}>Every hour</option>
                        </select>
                    </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">Task Sync</h4>
                        <p class="text-xs text-gray-400 mb-3">Sync tasks with external services</p>
                        <label class="flex items-center gap-2 mb-3">
                            <input type="checkbox" 
                                   ${this.taskSyncEnabled ? 'checked' : ''}
                                   onchange="dataLoader.setTaskSync(this.checked)"
                                   class="w-4 h-4 rounded">
                            <span>Enable Task Sync</span>
                        </label>
                        <select onchange="dataLoader.setTaskSyncService(this.value)" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
                                ${!this.taskSyncEnabled ? 'disabled' : ''}>
                            <option value="ticktick" ${this.taskSyncService === 'ticktick' ? 'selected' : ''}>TickTick</option>
                            <option value="todoist" ${this.taskSyncService === 'todoist' ? 'selected' : ''}>Todoist</option>
                        </select>
                    </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">AI Voice</h4>
                        <p class="text-xs text-gray-400 mb-3">Customize the AI assistant voice</p>
                        <select onchange="dataLoader.setAIVoice(this.value)" 
                                id="voice-selector"
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                            <option value="">Loading voices...</option>
                        </select>
                        <button onclick="dataLoader.testAIVoice()" 
                                class="w-full mt-2 bg-blue-600 hover:bg-blue-700 px-3 py-2 rounded text-sm">
                            🔊 Test Voice
                        </button>
                    </div>
                    
                    <div class="border-t border-gray-700 pt-4">
                        <h4 class="text-lg font-semibold mb-3">AI Personalization</h4>
                        <p class="text-xs text-gray-400 mb-3">Tell the AI about yourself for better responses</p>
                        <button onclick="dataLoader.showUserProfileModal()" 
                                class="w-full bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded">
                            ${this.userProfile?.preferred_name ? '✏️ Edit' : '➕ Create'} Your AI Profile
                        </button>
                    </div>
                </div>
                
                <button onclick="dataLoader.hideEditPanel()" 
                        class="w-full mt-6 bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
                    Save & Close
                </button>
            </div>
        `;
        document.body.appendChild(panel);
        
        // Populate voice options
        this.populateVoiceOptions();
    }
    
    hideEditPanel() {
        const panel = document.getElementById('edit-panel');
        if (panel) {
            panel.remove();
        }
        this.editMode = false;
        const btn = document.getElementById('edit-mode-btn');
        if (btn) {
            btn.innerHTML = '<span>⚙️</span><span>Edit Dashboard</span>';
            btn.className = 'w-full bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg text-sm flex items-center justify-center gap-2 mb-2';
        }
    }
    
    toggleSection(sectionName) {
        this.dashboardConfig[sectionName] = !this.dashboardConfig[sectionName];
        this.saveDashboardConfig();
        this.updateNavVisibility();
    }
    
    setAutoRefreshInterval(minutes) {
        this.autoRefreshInterval = parseInt(minutes);
        this.saveAutoRefreshSettings();
        this.startAutoRefresh();
        
        if (this.autoRefreshInterval === 0) {
            console.log('Auto-refresh disabled');
        } else {
            console.log(`Auto-refresh set to ${this.autoRefreshInterval} minutes`);
        }
    }
    
    setTaskSync(enabled) {
        this.taskSyncEnabled = enabled;
        this.saveTaskSyncSettings();
        console.log(`Task sync ${enabled ? 'enabled' : 'disabled'} for ${this.taskSyncService}`);
    }
    
    setTaskSyncService(service) {
        this.taskSyncService = service;
        this.saveTaskSyncSettings();
        console.log(`Task sync service set to ${service}`);
    }
    
    saveTaskSyncSettings() {
        localStorage.setItem('taskSyncSettings', JSON.stringify({
            enabled: this.taskSyncEnabled,
            service: this.taskSyncService
        }));
    }
    
    loadTaskSyncSettings() {
        const stored = localStorage.getItem('taskSyncSettings');
        if (stored) {
            const settings = JSON.parse(stored);
            this.taskSyncEnabled = settings.enabled || false;
            this.taskSyncService = settings.service || 'ticktick';
        }
    }
    
    // Voice Settings
    loadVoiceSettings() {
        const stored = localStorage.getItem('selectedVoice');
        if (stored) {
            this.selectedVoice = stored;
        }
        
        // Load available voices
        this.loadAvailableVoices();
        
        // Voices may not be loaded immediately, reload on voiceschanged event
        if (this.speechSynthesis) {
            this.speechSynthesis.onvoiceschanged = () => {
                this.loadAvailableVoices();
                // Set default voice if not already set
                if (!this.selectedVoice) {
                    this.setDefaultVoice();
                }
            };
        }
    }
    
    setDefaultVoice() {
        if (!this.availableVoices || this.availableVoices.length === 0) {
            return;
        }
        
        console.log('Available voices:', this.availableVoices.map(v => `${v.name} (${v.lang})`));
        
        // Priority order for voice selection
        const voicePriorities = [
            // Google voices (work best in Safari)
            v => v.name.includes('Google') && v.name.includes('US') && v.name.includes('Male'),
            v => v.name.includes('Google') && v.name.includes('UK') && v.name.includes('Male'),
            v => v.name.includes('Google') && v.name.includes('Male'),
            v => v.name.includes('Google') && v.lang.startsWith('en'),
            // Other quality English male voices
            v => v.name.toLowerCase().includes('alex'),  // macOS Alex voice
            v => v.lang === 'en-US' && v.name.toLowerCase().includes('male'),
            v => v.lang === 'en-GB' && v.name.toLowerCase().includes('male'),
            // Any English male voice
            v => v.lang.startsWith('en') && v.name.toLowerCase().includes('male'),
            // Any English voice
            v => v.lang.startsWith('en')
        ];
        
        // Try each priority until we find a voice
        for (const priorityFn of voicePriorities) {
            const voice = this.availableVoices.find(priorityFn);
            if (voice) {
                this.selectedVoice = voice.name;
                localStorage.setItem('selectedVoice', this.selectedVoice);
                console.log('✅ Default voice set to:', this.selectedVoice, `(${voice.lang})`);
                return;
            }
        }
        
        // Last resort: just use the first available voice
        if (this.availableVoices.length > 0) {
            this.selectedVoice = this.availableVoices[0].name;
            localStorage.setItem('selectedVoice', this.selectedVoice);
            console.log('⚠️ Fallback to first available voice:', this.selectedVoice);
        }
    }
    
    loadAvailableVoices() {
        if (this.speechSynthesis) {
            this.availableVoices = this.speechSynthesis.getVoices();
            
            // Filter to show only high-quality voices (prioritize Google voices)
            const googleVoices = this.availableVoices.filter(v => v.name.includes('Google'));
            const otherQualityVoices = this.availableVoices.filter(v => 
                !v.name.includes('Google') && 
                (v.name.toLowerCase().includes('alex') || 
                 v.lang.startsWith('en'))
            );
            
            console.log(`Loaded ${this.availableVoices.length} total voices (${googleVoices.length} Google voices)`);
            if (googleVoices.length > 0) {
                console.log('🎤 Google voices available:', googleVoices.map(v => v.name));
            }
            
            // Set default voice on first load if none selected
            if (!this.selectedVoice && this.availableVoices.length > 0) {
                this.setDefaultVoice();
            }
        }
    }
    
    populateVoiceOptions() {
        const selector = document.getElementById('voice-selector');
        if (!selector) return;
        
        if (this.availableVoices.length === 0) {
            // Try loading voices again
            this.loadAvailableVoices();
            
            // If still no voices, show message
            if (this.availableVoices.length === 0) {
                selector.innerHTML = '<option value="">No voices available</option>';
                return;
            }
        }
        
        // Populate dropdown with available voices
        selector.innerHTML = this.availableVoices.map((voice, index) => {
            const selected = this.selectedVoice === voice.name ? 'selected' : '';
            return `<option value="${voice.name}" ${selected}>${voice.name} (${voice.lang})</option>`;
        }).join('');
    }
    
    setAIVoice(voiceName) {
        this.selectedVoice = voiceName;
        localStorage.setItem('selectedVoice', voiceName);
        console.log(`AI voice set to: ${voiceName}`);
    }
    
    testAIVoice() {
        this.speakText('Hello! This is your AI assistant. How does my voice sound?');
    }
    
    updateNavVisibility() {
        Object.entries(this.dashboardConfig).forEach(([key, enabled]) => {
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                const linkText = link.textContent.trim().toLowerCase();
                if (linkText.includes(key)) {
                    link.style.display = enabled ? 'flex' : 'none';
                }
            });
        });
    }
    
    saveDashboardConfig() {
        localStorage.setItem('dashboardConfig', JSON.stringify(this.dashboardConfig));
    }
    
    loadDashboardConfig() {
        const stored = localStorage.getItem('dashboardConfig');
        if (stored) {
            try {
                this.dashboardConfig = { ...this.dashboardConfig, ...JSON.parse(stored) };
                this.updateNavVisibility();
            } catch (error) {
                console.error('Error loading dashboard config:', error);
            }
        }
    }
    
    loadAutoRefreshSettings() {
        const stored = localStorage.getItem('autoRefreshInterval');
        if (stored) {
            this.autoRefreshInterval = parseInt(stored);
        }
        this.startAutoRefresh();
    }
    
    saveAutoRefreshSettings() {
        localStorage.setItem('autoRefreshInterval', this.autoRefreshInterval.toString());
    }
    
    startAutoRefresh() {
        // Clear existing timer
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
        }
        
        // Update status display
        this.updateRefreshStatus();
        
        // Don't start if interval is 0 (disabled)
        if (this.autoRefreshInterval === 0) {
            return;
        }
        
        // Start new timer
        const intervalMs = this.autoRefreshInterval * 60 * 1000;
        this.autoRefreshTimer = setInterval(async () => {
            console.log('Auto-refreshing dashboard data...');
            await this.loadAllData();
            await this.generateOverviewPrompt();
            this.updateRefreshStatus();
        }, intervalMs);
        
        console.log(`Auto-refresh enabled: every ${this.autoRefreshInterval} minutes`);
    }
    
    updateRefreshStatus() {
        const statusEl = document.getElementById('refresh-status-text');
        if (!statusEl) return;
        
        if (this.autoRefreshInterval === 0) {
            statusEl.textContent = 'Auto-refresh: Disabled';
        } else {
            const lastUpdate = new Date().toLocaleTimeString();
            const nextUpdate = new Date(Date.now() + this.autoRefreshInterval * 60 * 1000).toLocaleTimeString();
            statusEl.textContent = `Auto-refresh: Every ${this.autoRefreshInterval}min | Last: ${lastUpdate} | Next: ${nextUpdate}`;
        }
    }
    
    async generateOverviewPrompt() {
        // Generate an AI prompt for the overview based on current data
        const activeTodos = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted');
        const upcomingEvents = this.calendar.filter(e => new Date(e.start) > new Date()).slice(0, 3);
        const highPriorityEmails = this.emails.filter(e => e.priority === 'high');
        
        const prompt = `Dashboard Update:\n\n` +
            `Tasks: ${activeTodos.length} active (${activeTodos.filter(t => t.priority === 'high').length} high priority)\n` +
            `Calendar: ${upcomingEvents.length} upcoming events\n` +
            `Emails: ${highPriorityEmails.length} high priority\n\n` +
            `Top Priorities:\n` +
            activeTodos.slice(0, 3).map(t => `- ${t.title}`).join('\n');
        
        console.log('Overview Prompt:', prompt);
        
        // Could optionally send to AI for suggestions
        // For now just log it
        return prompt;
    }
    
    async generateOverviewSummary() {
        // Generate a 5-minute overview summary for the AI Assistant page
        const activeTodos = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted');
        const highPriorityTodos = activeTodos.filter(t => t.priority === 'high');
        const startedTodos = activeTodos.filter(t => t.status === 'in_progress');
        const upcomingEvents = this.calendar.filter(e => new Date(e.start) > new Date());
        const todayEvents = upcomingEvents.filter(e => {
            const start = new Date(e.start);
            const today = new Date();
            return start.toDateString() === today.toDateString();
        });
        const highPriorityEmails = this.emails.filter(e => e.priority === 'high');
        const unreadEmails = this.emails.filter(e => !e.read);
        
        let summary = '<div class="space-y-2">';
        
        // Quick stats
        summary += `<div class="flex flex-wrap gap-4 mb-3">`;
        if (activeTodos.length > 0) {
            summary += `<span class="text-yellow-400">📋 ${activeTodos.length} active task${activeTodos.length !== 1 ? 's' : ''}</span>`;
        }
        if (highPriorityTodos.length > 0) {
            summary += `<span class="text-red-400">🔥 ${highPriorityTodos.length} high priority</span>`;
        }
        if (todayEvents.length > 0) {
            summary += `<span class="text-blue-400">📅 ${todayEvents.length} event${todayEvents.length !== 1 ? 's' : ''} today</span>`;
        }
        if (highPriorityEmails.length > 0) {
            summary += `<span class="text-purple-400">📧 ${highPriorityEmails.length} important email${highPriorityEmails.length !== 1 ? 's' : ''}</span>`;
        }
        summary += `</div>`;
        
        // Top priorities
        if (highPriorityTodos.length > 0) {
            summary += `<div class="mt-3"><strong class="text-red-400">🎯 Top Priorities:</strong><ul class="list-disc list-inside ml-4 mt-1">`;
            highPriorityTodos.slice(0, 3).forEach(todo => {
                summary += `<li class="text-gray-300">${this.escapeHtml(todo.title)}</li>`;
            });
            summary += `</ul></div>`;
        }
        
        // In progress
        if (startedTodos.length > 0) {
            summary += `<div class="mt-3"><strong class="text-green-400">🚀 In Progress:</strong><ul class="list-disc list-inside ml-4 mt-1">`;
            startedTodos.slice(0, 3).forEach(todo => {
                summary += `<li class="text-gray-300">${this.escapeHtml(todo.title)}</li>`;
            });
            summary += `</ul></div>`;
        }
        
        // Today's events
        if (todayEvents.length > 0) {
            summary += `<div class="mt-3"><strong class="text-blue-400">📅 Today's Events:</strong><ul class="list-disc list-inside ml-4 mt-1">`;
            todayEvents.slice(0, 3).forEach(event => {
                const time = new Date(event.start).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
                summary += `<li class="text-gray-300">${time} - ${this.escapeHtml(event.title)}</li>`;
            });
            summary += `</ul></div>`;
        }
        
        // Summary message
        if (activeTodos.length === 0 && todayEvents.length === 0) {
            summary += `<p class="text-green-400 mt-3">✨ You're all caught up! Great work!</p>`;
        } else if (highPriorityTodos.length === 0 && startedTodos.length > 0) {
            summary += `<p class="text-green-400 mt-3">💪 Making progress! Keep up the momentum.</p>`;
        } else if (highPriorityTodos.length > 0) {
            summary += `<p class="text-yellow-400 mt-3">⚡ Focus on high priority items to stay ahead.</p>`;
        }
        
        summary += '</div>';
        
        this.overviewSummary = summary;
    }
    
    generatePersonalizedSuggestion() {
        // Generate a random personalized suggestion based on user profile and activity
        const suggestions = [];
        
        // Check user profile for interests
        if (this.userProfile && this.userProfile.interests) {
            const interests = this.userProfile.interests.split(',').map(i => i.trim()).filter(Boolean);
            if (interests.length > 0) {
                const randomInterest = interests[Math.floor(Math.random() * interests.length)];
                suggestions.push({
                    title: `Explore ${randomInterest}`,
                    description: `Based on your interest in ${randomInterest}, consider setting aside time to dive deeper into this topic today.`,
                    action: null
                });
            }
        }
        
        // Check for sections not visited recently
        const now = new Date();
        const sections = ['emails', 'calendar', 'news', 'music', 'github'];
        const unvisitedSections = sections.filter(section => {
            if (this.dashboardConfig && this.dashboardConfig.sections && 
                this.dashboardConfig.sections[section] === false) {
                return false; // Don't suggest disabled sections
            }
            return true;
        });
        
        if (unvisitedSections.length > 0) {
            const randomSection = unvisitedSections[Math.floor(Math.random() * unvisitedSections.length)];
            const sectionNames = {
                emails: '📧 Emails',
                calendar: '📅 Calendar', 
                news: '📰 News',
                music: '🎵 Music',
                github: '💻 GitHub'
            };
            suggestions.push({
                title: `Check ${sectionNames[randomSection]}`,
                description: `You might have updates in your ${randomSection} section. Take a quick look!`,
                action: randomSection,
                actionLabel: `View ${sectionNames[randomSection]}`
            });
        }
        
        // Time-based suggestions
        const hour = now.getHours();
        if (hour >= 6 && hour < 9) {
            suggestions.push({
                title: 'Morning Planning',
                description: 'Start your day strong! Review your top 3 priorities and schedule time for focused work.',
                action: 'todos',
                actionLabel: 'Review Tasks'
            });
        } else if (hour >= 12 && hour < 14) {
            suggestions.push({
                title: 'Midday Check-in',
                description: 'Take a break and review your progress. Are you on track with your priorities?',
                action: null
            });
        } else if (hour >= 17 && hour < 19) {
            suggestions.push({
                title: 'End-of-Day Wrap-up',
                description: 'Review what you accomplished today and set up tomorrow for success.',
                action: 'todos',
                actionLabel: 'Review Progress'
            });
        }
        
        // Activity-based suggestions
        const completedToday = this.todos.filter(t => {
            if (t.status !== 'completed' || !t.completed_at) return false;
            const completed = new Date(t.completed_at);
            return completed.toDateString() === now.toDateString();
        });
        
        if (completedToday.length >= 5) {
            suggestions.push({
                title: '🎉 Productivity Streak!',
                description: `You've completed ${completedToday.length} tasks today! You're on fire! Keep the momentum going.`,
                action: null
            });
        }
        
        const highPriorityTodos = this.todos.filter(t => t.status !== 'completed' && t.status !== 'deleted' && t.priority === 'high');
        if (highPriorityTodos.length > 5) {
            suggestions.push({
                title: '🎯 Focus Strategy',
                description: `You have ${highPriorityTodos.length} high priority tasks. Consider breaking them down or delegating some to stay focused.`,
                action: 'todos',
                actionLabel: 'Review Priorities'
            });
        }
        
        // Feedback-based suggestions
        const likedItems = Object.entries(this.feedbackData).filter(([key, value]) => value === 'up');
        if (likedItems.length > 10) {
            suggestions.push({
                title: '💡 Pattern Recognition',
                description: 'You\'ve given lots of positive feedback! The AI is learning your preferences to provide better suggestions.',
                action: null
            });
        }
        
        // Select random suggestion
        if (suggestions.length > 0) {
            this.personalizedSuggestion = suggestions[Math.floor(Math.random() * suggestions.length)];
        }
    }
    
    handlePersonalizedAction(action) {
        // Handle action from personalized suggestion
        if (action && typeof showSection === 'function') {
            showSection(action);
        }
    }
    
    // BACKGROUND IMAGE SYSTEM
    loadBackgroundSettings() {
        const stored = localStorage.getItem('backgroundSettings');
        if (stored) {
            const settings = JSON.parse(stored);
            this.backgroundImages = settings.images || [];
            this.currentBackgroundIndex = settings.currentIndex || 0;
            this.backgroundRotation = settings.rotation || 'random';
            this.fullPageBackground = settings.fullPageBackground || false;
        }
        
        // Load saved backgrounds
        this.loadSavedBackgrounds();
        
        // Initialize with default sci-fi images if none saved
        if (this.backgroundImages.length === 0) {
            this.backgroundImages = [
                { url: 'https://images.unsplash.com/photo-1419242902214-272b3f66ee7a', name: 'Space Nebula', theme: 'dark' },
                { url: 'https://images.unsplash.com/photo-1462331940025-496dfbfc7564', name: 'Night Sky', theme: 'dark' },
                { url: 'https://images.unsplash.com/photo-1446776653964-20c1d3a81b06', name: 'Cosmos', theme: 'dark' },
                { url: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa', name: 'Earth Space', theme: 'blue' },
                { url: 'https://images.unsplash.com/photo-1502134249126-9f3755a50d78', name: 'Galaxy', theme: 'purple' }
            ];
        }
        
        this.applyBackground();
    }
    
    saveBackgroundSettings() {
        const settings = {
            images: this.backgroundImages,
            currentIndex: this.currentBackgroundIndex,
            rotation: this.backgroundRotation,
            fullPageBackground: this.fullPageBackground
        };
        localStorage.setItem('backgroundSettings', JSON.stringify(settings));
    }
    
    applyBackground() {
        if (this.backgroundImages.length === 0) return;
        
        const image = this.backgroundImages[this.currentBackgroundIndex];
        
        // Apply to ALL visible sections if full-page background is enabled
        if (this.fullPageBackground) {
            const allSections = document.querySelectorAll('.section-content:not(.hidden)');
            allSections.forEach(section => {
                section.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.85)), url(${image.url}?w=1920&q=85)`;
                section.style.backgroundSize = 'cover';
                section.style.backgroundPosition = 'center';
                section.style.backgroundAttachment = 'fixed';
                
                // Make all cards semi-transparent
                const cards = section.querySelectorAll('.bg-gray-800, .bg-gray-700');
                cards.forEach(card => {
                    card.style.backgroundColor = 'rgba(31, 41, 55, 0.85)';
                    card.style.webkitBackdropFilter = 'blur(10px)';
                    card.style.backdropFilter = 'blur(10px)';
                });
            });
        }
        
        // Apply header image to overview section specifically
        const section = document.getElementById('section-overview');
        if (!section) return;
        
        const header = section.querySelector('.max-w-7xl');
        if (header) {
            // Create header image container if it doesn't exist
            let headerImage = document.getElementById('overview-header-image');
            if (!headerImage) {
                headerImage = document.createElement('div');
                headerImage.id = 'overview-header-image';
                headerImage.className = 'relative rounded-xl overflow-hidden mb-8 h-64';
                header.insertBefore(headerImage, header.firstChild);
            }
            
            // Apply background image with gradient overlay to header
            headerImage.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.7)), url(${image.url}?w=1200&q=80)`;
            headerImage.style.backgroundSize = 'cover';
            headerImage.style.backgroundPosition = 'center';
            
            // Add title overlay
            headerImage.innerHTML = `
                <div class="absolute inset-0 flex flex-col justify-end p-6">
                    <h2 class="text-4xl font-bold text-white mb-2">Dashboard Overview</h2>
                    <div class="flex gap-2 items-center flex-wrap">
                        <span class="text-sm text-gray-300">${image.name}</span>
                        <div class="ml-auto flex gap-2">
                            <button onclick="dataLoader.giveBackgroundFeedback('up')" 
                                    class="bg-white/20 hover:bg-green-500/80 backdrop-blur-sm px-3 py-1 rounded text-lg">
                                👍
                            </button>
                            <button onclick="dataLoader.giveBackgroundFeedback('neutral')" 
                                    class="bg-white/20 hover:bg-yellow-500/80 backdrop-blur-sm px-3 py-1 rounded text-lg">
                                👌
                            </button>
                            <button onclick="dataLoader.giveBackgroundFeedback('down')" 
                                    class="bg-white/20 hover:bg-red-500/80 backdrop-blur-sm px-3 py-1 rounded text-lg">
                                👎
                            </button>
                            <button onclick="dataLoader.nextBackground()" 
                                    class="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-1 rounded text-sm text-white">
                                🔄 Change
                            </button>
                            <button onclick="dataLoader.openBackgroundSettings()" 
                                    class="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-1 rounded text-sm text-white">
                                ⚙️ Settings
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // Apply full-page background to overview if enabled
        if (this.fullPageBackground) {
            // Apply full-page background
            section.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.85)), url(${image.url}?w=1920&q=85)`;
            section.style.backgroundSize = 'cover';
            section.style.backgroundPosition = 'center';
            section.style.backgroundAttachment = 'fixed';
            
            // Make all cards semi-transparent
            const cards = section.querySelectorAll('.bg-gray-800, .bg-gray-700');
            cards.forEach(card => {
                card.style.backgroundColor = 'rgba(31, 41, 55, 0.85)';
                card.style.webkitBackdropFilter = 'blur(10px)'; // Safari support
                card.style.backdropFilter = 'blur(10px)';
            });
            
            // Create floating controls
            let controls = document.getElementById('background-controls');
            if (!controls) {
                controls = document.createElement('div');
                controls.id = 'background-controls';
                controls.className = 'fixed top-20 right-4 bg-gray-800/90 backdrop-blur-sm rounded-lg p-3 z-40 shadow-lg';
                controls.innerHTML = `
                    <div class="flex flex-col gap-2">
                        <span class="text-xs text-gray-400">${image.name}</span>
                        <div class="flex gap-2">
                            <button onclick="dataLoader.giveBackgroundFeedback('up')" 
                                    class="bg-gray-700 hover:bg-green-600 px-2 py-1 rounded text-sm">👍</button>
                            <button onclick="dataLoader.giveBackgroundFeedback('neutral')" 
                                    class="bg-gray-700 hover:bg-yellow-600 px-2 py-1 rounded text-sm">👌</button>
                            <button onclick="dataLoader.giveBackgroundFeedback('down')" 
                                    class="bg-gray-700 hover:bg-red-600 px-2 py-1 rounded text-sm">👎</button>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="dataLoader.nextBackground()" 
                                    class="bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-xs">� Change</button>
                            <button onclick="dataLoader.openBackgroundSettings()" 
                                    class="bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-xs">⚙️ Settings</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(controls);
            } else {
                // Update controls text
                const nameSpan = controls.querySelector('.text-gray-400');
                if (nameSpan) nameSpan.textContent = image.name;
            }
        } else {
            // No full-page background - clear section background
            section.style.backgroundImage = '';
            section.style.backgroundColor = '';
            
            // Reset card transparency
            const cards = section.querySelectorAll('.bg-gray-800, .bg-gray-700');
            cards.forEach(card => {
                card.style.backgroundColor = '';
                card.style.webkitBackdropFilter = ''; // Safari support
                card.style.backdropFilter = '';
            });
            
            // Remove floating controls
            const controls = document.getElementById('background-controls');
            if (controls) controls.remove();
        }
        
        // Apply theme adjustment based on image
        this.adjustTheme(image.theme);
    }
    
    adjustTheme(theme) {
        const root = document.documentElement;
        
        switch(theme) {
            case 'blue':
                root.style.setProperty('--accent-color', '#3b82f6');
                break;
            case 'purple':
                root.style.setProperty('--accent-color', '#a855f7');
                break;
            case 'dark':
            default:
                root.style.setProperty('--accent-color', '#6366f1');
                break;
        }
    }
    
    nextBackground() {
        if (this.backgroundImages.length === 0) return;
        
        if (this.backgroundRotation === 'random') {
            this.currentBackgroundIndex = Math.floor(Math.random() * this.backgroundImages.length);
        } else {
            this.currentBackgroundIndex = (this.currentBackgroundIndex + 1) % this.backgroundImages.length;
        }
        
        this.saveBackgroundSettings();
        this.applyBackground();
    }
    
    openBackgroundSettings() {
        const modal = `
            <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto" onclick="if(event.target===this) this.remove()">
                <div class="bg-gray-800 rounded-xl p-6 max-w-3xl w-full my-8">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-2xl font-bold">Background Settings</h3>
                        <button onclick="this.closest('.fixed').remove()" 
                                class="text-gray-400 hover:text-white text-2xl leading-none">
                            ×
                        </button>
                    </div>
                    
                    <div class="max-h-[calc(90vh-8rem)] overflow-y-auto pr-2 space-y-6">
                    
                    <div class="mb-6">
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="checkbox" 
                                   ${this.fullPageBackground ? 'checked' : ''}
                                   onchange="dataLoader.toggleFullPageBackground(this.checked)"
                                   class="w-5 h-5 rounded">
                            <div>
                                <div class="font-semibold">Full-Page Background</div>
                                <div class="text-xs text-gray-400">Apply background to entire overview page with transparent cards</div>
                            </div>
                        </label>
                    </div>
                    
                    <div class="mb-6">
                        <label class="block text-sm font-medium mb-2">Rotation Mode</label>
                        <select onchange="dataLoader.setBackgroundRotation(this.value)" 
                                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2">
                            <option value="random" ${this.backgroundRotation === 'random' ? 'selected' : ''}>Random</option>
                            <option value="sequential" ${this.backgroundRotation === 'sequential' ? 'selected' : ''}>Sequential</option>
                            <option value="fixed" ${this.backgroundRotation === 'fixed' ? 'selected' : ''}>Fixed (Current Only)</option>
                        </select>
                    </div>
                    
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold mb-3">Add New Backgrounds</h4>
                        <div class="grid grid-cols-2 gap-3">
                            <button onclick="dataLoader.fetchNewBackgroundFromUnsplash()" 
                                    class="bg-purple-600 hover:bg-purple-700 px-4 py-3 rounded-lg flex items-center justify-center gap-2">
                                <span>🌌</span>
                                <span>Fetch from Unsplash</span>
                            </button>
                            <label class="bg-blue-600 hover:bg-blue-700 px-4 py-3 rounded-lg flex items-center justify-center gap-2 cursor-pointer">
                                <span>📤</span>
                                <span>Upload Custom</span>
                                <input type="file" 
                                       accept="image/*" 
                                       onchange="dataLoader.uploadCustomBackground(event)" 
                                       class="hidden">
                            </label>
                        </div>
                    </div>
                    
                    ${this.savedBackgrounds.length > 0 ? `
                        <div class="mb-6">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="text-lg font-semibold">💾 Saved Backgrounds (${this.savedBackgrounds.length})</h4>
                                <button onclick="dataLoader.clearSavedBackgrounds()" 
                                        class="text-xs text-red-400 hover:text-red-300">
                                    Clear All
                                </button>
                            </div>
                            <p class="text-xs text-gray-400 mb-3">These images are saved offline and ready to use</p>
                            <div class="grid grid-cols-3 gap-3 max-h-64 overflow-y-auto">
                                ${this.savedBackgrounds.map((img, idx) => `
                                    <div class="relative group">
                                        <img src="${img.url}" 
                                             onclick="dataLoader.useSavedBackground(${idx})"
                                             class="w-full h-24 object-cover rounded cursor-pointer" 
                                             alt="${img.name}">
                                        <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center rounded transition-opacity">
                                            <span class="text-white text-xs">${img.name}</span>
                                        </div>
                                        <button onclick="event.stopPropagation(); dataLoader.removeSavedBackground(${idx})" 
                                                class="absolute top-1 right-1 bg-red-600 hover:bg-red-700 text-white text-xs w-5 h-5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                                            ×
                                        </button>
                                        <span class="absolute top-1 left-1 bg-green-600 text-xs px-1 rounded">✓</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold mb-3">Available Backgrounds</h4>
                        <div class="grid grid-cols-3 gap-3">
                            ${this.backgroundImages.map((img, idx) => `
                                <div class="relative group cursor-pointer ${idx === this.currentBackgroundIndex ? 'ring-2 ring-blue-500' : ''}" 
                                     onclick="dataLoader.selectBackground(${idx})">
                                    <img src="${img.url}?w=300&h=200&fit=crop" 
                                         class="w-full h-24 object-cover rounded" 
                                         alt="${img.name}">
                                    <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center rounded transition-opacity">
                                        <span class="text-white text-xs">${img.name}</span>
                                    </div>
                                    ${idx === this.currentBackgroundIndex ? '<span class="absolute top-1 right-1 bg-blue-600 text-xs px-1 rounded">▶</span>' : ''}
                                    <button onclick="event.stopPropagation(); dataLoader.removeBackground(${idx})" 
                                            class="absolute top-1 left-1 bg-red-600 hover:bg-red-700 text-white text-xs w-5 h-5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                                        ×
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    </div>
                    
                    <div class="mt-6 pt-4 border-t border-gray-700">
                        <button onclick="this.closest('.fixed').remove()" 
                                class="w-full bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modal);
    }
    
    toggleFullPageBackground(enabled) {
        this.fullPageBackground = enabled;
        this.saveBackgroundSettings();
        this.applyBackground();
        this.showNotification(enabled ? '🌌 Full-page background enabled!' : '📸 Header-only background enabled');
    }
    
    useSavedBackground(index) {
        if (index < 0 || index >= this.savedBackgrounds.length) return;
        
        const savedBg = this.savedBackgrounds[index];
        
        // Check if already in current backgrounds
        const exists = this.backgroundImages.find(img => img.name === savedBg.name);
        if (!exists) {
            this.backgroundImages.push(savedBg);
        }
        
        // Set as current
        this.currentBackgroundIndex = this.backgroundImages.findIndex(img => img.name === savedBg.name);
        this.saveBackgroundSettings();
        this.applyBackground();
        
        // Close modal
        const modal = document.querySelector('.fixed.inset-0');
        if (modal) modal.remove();
        
        this.showNotification(`Using saved background: ${savedBg.name}`);
    }
    
    async fetchNewBackgroundFromUnsplash() {
        try {
            this.showNotification('🌌 Fetching new background from Unsplash...');
            
            // Fetch random space/sci-fi image from Unsplash
            const topics = ['space', 'galaxy', 'nebula', 'cosmos', 'stars', 'universe', 'astronomy', 'planet'];
            const randomTopic = topics[Math.floor(Math.random() * topics.length)];
            
            // Using Unsplash Source API with timestamp to ensure unique fetch
            const timestamp = Date.now();
            const url = `https://source.unsplash.com/1600x900/?${randomTopic}&sig=${timestamp}`;
            
            // Create a new image object
            const newImage = {
                url: url,
                name: `${randomTopic.charAt(0).toUpperCase() + randomTopic.slice(1)} ${new Date().toLocaleTimeString()}`,
                theme: 'dark'
            };
            
            this.backgroundImages.push(newImage);
            this.currentBackgroundIndex = this.backgroundImages.length - 1;
            this.saveBackgroundSettings();
            this.applyBackground();
            
            // Close and reopen modal to show new image
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification(`✅ Added new ${randomTopic} background!`);
        } catch (error) {
            console.error('Error fetching new background:', error);
            this.showNotification('⚠️ Could not fetch new background from Unsplash');
        }
    }
    
    async uploadCustomBackground(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        // Validate file type
        if (!file.type.startsWith('image/')) {
            this.showNotification('⚠️ Please select an image file');
            return;
        }
        
        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            this.showNotification('⚠️ Image too large. Please select an image under 5MB');
            return;
        }
        
        try {
            this.showNotification('📤 Uploading custom background...');
            
            // Convert to base64
            const reader = new FileReader();
            reader.onload = (e) => {
                const base64url = e.target.result;
                
                // Create new image object
                const newImage = {
                    url: base64url,
                    name: `Custom: ${file.name.split('.')[0]}`,
                    theme: 'custom',
                    custom: true
                };
                
                // Add to backgrounds
                this.backgroundImages.push(newImage);
                this.currentBackgroundIndex = this.backgroundImages.length - 1;
                this.saveBackgroundSettings();
                this.applyBackground();
                
                // Close and reopen modal to show new image
                const modal = document.querySelector('.fixed.inset-0');
                if (modal) {
                    modal.remove();
                    this.openBackgroundSettings();
                }
                
                this.showNotification(`✅ Custom background "${file.name}" uploaded!`);
            };
            
            reader.onerror = () => {
                this.showNotification('⚠️ Error reading image file');
            };
            
            reader.readAsDataURL(file);
        } catch (error) {
            console.error('Error uploading custom background:', error);
            this.showNotification('⚠️ Could not upload custom background');
        }
    }
    
    removeBackground(index) {
        if (index < 0 || index >= this.backgroundImages.length) return;
        
        const image = this.backgroundImages[index];
        if (confirm(`Remove "${image.name}" from backgrounds?`)) {
            this.backgroundImages.splice(index, 1);
            
            // Adjust current index if needed
            if (this.currentBackgroundIndex >= this.backgroundImages.length) {
                this.currentBackgroundIndex = Math.max(0, this.backgroundImages.length - 1);
            }
            
            this.saveBackgroundSettings();
            this.applyBackground();
            
            // Reopen modal to update view
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification(`🗑️ Removed "${image.name}"`);
        }
    }
    
    removeSavedBackground(index) {
        if (index < 0 || index >= this.savedBackgrounds.length) return;
        
        const image = this.savedBackgrounds[index];
        if (confirm(`Remove "${image.name}" from saved backgrounds?`)) {
            this.savedBackgrounds.splice(index, 1);
            localStorage.setItem('savedBackgrounds', JSON.stringify(this.savedBackgrounds));
            
            // Reopen modal to update view
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification(`🗑️ Removed "${image.name}" from saved`);
        }
    }
    
    clearSavedBackgrounds() {
        if (confirm(`Clear all ${this.savedBackgrounds.length} saved backgrounds? This cannot be undone.`)) {
            this.savedBackgrounds = [];
            localStorage.setItem('savedBackgrounds', JSON.stringify(this.savedBackgrounds));
            
            // Reopen modal to update view
            const modal = document.querySelector('.fixed.inset-0');
            if (modal) {
                modal.remove();
                this.openBackgroundSettings();
            }
            
            this.showNotification('🗑️ All saved backgrounds cleared');
        }
    }
    
    setBackgroundRotation(mode) {
        this.backgroundRotation = mode;
        this.saveBackgroundSettings();
    }
    
    selectBackground(index) {
        this.currentBackgroundIndex = index;
        this.saveBackgroundSettings();
        this.applyBackground();
        document.querySelector('.fixed.inset-0')?.remove();
    }
    
    async giveBackgroundFeedback(sentiment) {
        const currentImage = this.backgroundImages[this.currentBackgroundIndex];
        const key = `background-${currentImage.url}`;
        
        // Store feedback
        this.feedbackData[key] = sentiment;
        localStorage.setItem('dashboardFeedback', JSON.stringify(this.feedbackData));
        
        // Send to backend for AI training
        try {
            await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    item_type: 'background',
                    item_id: currentImage.url,
                    sentiment: sentiment,
                    context: {
                        name: currentImage.name,
                        theme: currentImage.theme,
                        url: currentImage.url
                    }
                })
            });
        } catch (error) {
            console.error('Error sending background feedback:', error);
        }
        
        // Handle feedback actions
        if (sentiment === 'up') {
            // Save the image as base64 for offline use
            await this.saveBackgroundOffline(currentImage);
            this.showNotification('👍 Background saved for offline use!');
        } else if (sentiment === 'down') {
            // Remove from collection and load new one
            this.backgroundImages.splice(this.currentBackgroundIndex, 1);
            
            // Load a new background from Unsplash
            await this.fetchNewBackground();
            
            // Adjust index if needed
            if (this.currentBackgroundIndex >= this.backgroundImages.length) {
                this.currentBackgroundIndex = 0;
            }
            
            this.saveBackgroundSettings();
            this.applyBackground();
            this.showNotification('👎 Background removed. Loading a new one...');
        } else {
            // Neutral - just move to next
            this.nextBackground();
            this.showNotification('👌 Noted! Moving to next background.');
        }
    }
    
    async saveBackgroundOffline(image) {
        try {
            // Convert image URL to base64
            const response = await fetch(image.url);
            const blob = await response.blob();
            
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64data = reader.result;
                    
                    // Save to savedBackgrounds array
                    const savedImage = {
                        url: base64data,
                        name: image.name,
                        theme: image.theme,
                        saved_at: new Date().toISOString()
                    };
                    
                    this.savedBackgrounds.push(savedImage);
                    
                    // Save to localStorage
                    localStorage.setItem('savedBackgrounds', JSON.stringify(this.savedBackgrounds));
                    
                    console.log('Background saved offline:', image.name);
                    resolve();
                };
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        } catch (error) {
            console.error('Error saving background offline:', error);
            this.showNotification('⚠️ Could not save background offline');
        }
    }
    
    loadSavedBackgrounds() {
        const stored = localStorage.getItem('savedBackgrounds');
        if (stored) {
            this.savedBackgrounds = JSON.parse(stored);
            console.log(`Loaded ${this.savedBackgrounds.length} saved backgrounds`);
        }
    }
    
    async fetchNewBackground() {
        try {
            // Fetch random space/sci-fi image from Unsplash
            const topics = ['space', 'galaxy', 'nebula', 'cosmos', 'stars', 'universe'];
            const randomTopic = topics[Math.floor(Math.random() * topics.length)];
            
            // Using Unsplash Source API for random images
            const url = `https://source.unsplash.com/1600x900/?${randomTopic}`;
            
            // Create a new image object
            const newImage = {
                url: url,
                name: `${randomTopic.charAt(0).toUpperCase() + randomTopic.slice(1)} View`,
                theme: 'dark'
            };
            
            this.backgroundImages.push(newImage);
            this.currentBackgroundIndex = this.backgroundImages.length - 1;
            
            console.log('Fetched new background:', newImage.name);
        } catch (error) {
            console.error('Error fetching new background:', error);
            this.showNotification('⚠️ Could not load new background. Using existing ones.');
        }
    }
    
    downloadBackgroundImage(image) {
        // Create a download link
        const link = document.createElement('a');
        link.href = `${image.url}?w=1920&q=90&dl=${encodeURIComponent(image.name)}.jpg`;
        link.download = `${image.name.replace(/\s+/g, '_')}.jpg`;
        link.target = '_blank';
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        console.log('Downloaded background:', image.name);
    }
    
    showNotification(message) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 bg-gray-800 border border-gray-700 rounded-lg px-6 py-3 shadow-lg z-50 animate-slide-in';
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.add('opacity-0', 'transition-opacity', 'duration-500');
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }
    
    // FEEDBACK SYSTEM
    async giveFeedback(itemType, itemId, sentiment) {
        const key = `${itemType}-${itemId}`;
        this.feedbackData[key] = sentiment;
        
        // Store feedback locally
        localStorage.setItem('dashboardFeedback', JSON.stringify(this.feedbackData));
        
        // Get item details for context
        let itemDetails = {};
        switch(itemType) {
            case 'todo':
                const todo = this.todos.find(t => t.id === itemId);
                if (todo) itemDetails = { title: todo.title, priority: todo.priority, source: todo.source };
                break;
            case 'event':
                const event = this.calendar.find(e => e.event_id === itemId);
                if (event) itemDetails = { title: event.summary || event.title, location: event.location, organizer: event.organizer };
                break;
            case 'email':
                const email = this.emails.find(e => e.id === itemId);
                if (email) itemDetails = { sender: email.sender, subject: email.subject, priority: email.priority, has_todos: email.has_todos };
                break;
            case 'news':
                const article = this.news.find(n => n.id === itemId);
                if (article) itemDetails = { title: article.title, source: article.source, category: article.category };
                break;
            case 'suggestion':
                const suggestion = this.aiSuggestions.find(s => s.id === itemId);
                if (suggestion) itemDetails = { title: suggestion.title, action: suggestion.action, source: suggestion.source };
                break;
            case 'vanity':
                const alert = this.vanityAlerts.find(v => v.id === itemId);
                if (alert) itemDetails = { title: alert.title, type: alert.type, source: alert.source };
                break;
            case 'music':
                const music = this.musicNews.find(m => m.id === itemId);
                if (music) itemDetails = { title: music.title, artist: music.artist, type: music.type };
                break;
        }
        
        // Send to backend for AI training
        try {
            await fetch('/api/ai/training/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    item_type: itemType,
                    item_id: itemId,
                    sentiment: sentiment,
                    item_details: itemDetails,
                    timestamp: new Date().toISOString()
                })
            });
            
            console.log(`Feedback recorded: ${itemType} ${itemId} - ${sentiment}`);
        } catch (error) {
            console.error('Error sending feedback:', error);
        }
        
        // Re-render the appropriate section to update button states
        switch(itemType) {
            case 'todo':
                this.renderTodos();
                break;
            case 'event':
                this.renderCalendar();
                break;
            case 'email':
                this.renderEmails();
                break;
            case 'news':
                this.renderNews();
                break;
            case 'suggestion':
                this.renderAISuggestions();
                break;
            case 'vanity':
                this.renderVanityAlerts();
                break;
            case 'music':
                this.renderMusicNews();
                break;
        }
    }
    
    async markEmailAsSafe(senderEmail) {
        try {
            const response = await fetch('/api/email/mark-safe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sender_email: senderEmail,
                    reason: 'User marked as safe from dashboard'
                })
            });
            
            if (response.ok) {
                console.log(`Marked ${senderEmail} as safe`);
                // Reload emails to update UI
                await this.loadEmails(true);
                
                // Show success message
                alert(`✓ ${senderEmail} has been added to your safe senders list. Future emails from this sender will be trusted.`);
            } else {
                throw new Error('Failed to mark sender as safe');
            }
        } catch (error) {
            console.error('Error marking email as safe:', error);
            alert('Failed to mark sender as safe. Please try again.');
        }
    }
    
    // Smart Email Tagging based on feedback patterns
    analyzeEmailTags() {
        const emailFeedback = {};
        
        // Group feedback by sender domain
        Object.entries(this.feedbackData).forEach(([key, sentiment]) => {
            if (key.startsWith('email-')) {
                const emailId = key.substring(6);
                const email = this.emails.find(e => e.id === emailId);
                if (email) {
                    const domain = email.sender.split('@')[1] || email.sender;
                    if (!emailFeedback[domain]) {
                        emailFeedback[domain] = { likes: 0, dislikes: 0, neutral: 0 };
                    }
                    
                    if (sentiment === 'like') emailFeedback[domain].likes++;
                    else if (sentiment === 'down') emailFeedback[domain].dislikes++;
                    else emailFeedback[domain].neutral++;
                }
            }
        });
        
        // Generate smart tags based on patterns
        const smartTags = {};
        Object.entries(emailFeedback).forEach(([domain, counts]) => {
            const total = counts.likes + counts.dislikes + counts.neutral;
            if (total >= 3) { // Need at least 3 feedbacks to establish pattern
                if (counts.likes / total > 0.7) {
                    smartTags[domain] = '⭐ Important';
                } else if (counts.dislikes / total > 0.7) {
                    smartTags[domain] = '🚫 Spam';
                } else if (counts.neutral / total > 0.7) {
                    smartTags[domain] = '📰 Newsletter';
                }
            }
        });
        
        return smartTags;
    }
    
    getSmartTagForEmail(email) {
        const smartTags = this.analyzeEmailTags();
        const domain = email.sender.split('@')[1] || email.sender;
        return smartTags[domain] || null;
    }
    
    loadFeedbackFromStorage() {
        const stored = localStorage.getItem('dashboardFeedback');
        if (stored) {
            try {
                this.feedbackData = JSON.parse(stored);
            } catch (error) {
                console.error('Error loading feedback:', error);
            }
        }
    }
}

// Global instance
const dataLoader = new DashboardDataLoader();

// Dashboard Management Functions
function showAddDashboardModal(dashboardData = null) {
    const modal = document.getElementById('add-dashboard-modal');
    const titleText = document.getElementById('modal-title-text');
    const saveBtnText = document.getElementById('save-btn-text');
    const form = document.getElementById('add-dashboard-form');
    
    if (dashboardData) {
        // Edit mode
        titleText.textContent = 'Edit Dashboard Configuration';
        saveBtnText.textContent = 'Save Changes';
        
        // Populate form with existing data
        document.getElementById('dashboard-id').value = dashboardData.id || '';
        document.getElementById('dashboard-name').value = dashboardData.name || '';
        document.getElementById('dashboard-path').value = dashboardData.path || '';
        document.getElementById('dashboard-type').value = dashboardData.type || 'forgeweb';
        document.getElementById('dashboard-port').value = dashboardData.port || '';
        document.getElementById('dashboard-command').value = dashboardData.start_command || '';
        document.getElementById('dashboard-production-url').value = dashboardData.production_url || '';
        document.getElementById('dashboard-api-url').value = dashboardData.api_url || '';
        document.getElementById('dashboard-active').checked = dashboardData.active !== false;
    } else {
        // Add mode
        titleText.textContent = 'Add Marketing Dashboard / Website';
        saveBtnText.textContent = 'Add Dashboard';
        form.reset();
        document.getElementById('dashboard-active').checked = true;
        
        // Set default type to forgeweb
        document.getElementById('dashboard-type').value = 'forgeweb';
        updateProjectTypeDefaults();
    }
    
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeAddDashboardModal() {
    const modal = document.getElementById('add-dashboard-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    // Reset form
    document.getElementById('add-dashboard-form').reset();
    document.getElementById('dashboard-id').value = '';
}

function updateProjectTypeDefaults() {
    const type = document.getElementById('dashboard-type').value;
    const portInput = document.getElementById('dashboard-port');
    const commandInput = document.getElementById('dashboard-command');
    const pathInput = document.getElementById('dashboard-path').value || '';
    
    // Default ports and commands for each type
    const defaults = {
        'forgeweb': {
            port: 8000,
            command: `python3 -m http.server 8000`
        },
        'forgemarket': {
            port: 8001,
            command: `python3 -m http.server 8001`
        },
        'flask': {
            port: 5000,
            command: `python app.py`
        },
        'fastapi': {
            port: 8000,
            command: `uvicorn main:app --reload --port 8000`
        },
        'react': {
            port: 3000,
            command: `npm start`
        },
        'vue': {
            port: 8080,
            command: `npm run serve`
        },
        'static': {
            port: 8000,
            command: `python3 -m http.server 8000`
        },
        'streamlit': {
            port: 8501,
            command: `streamlit run streamlit_app.py --server.port 8501`
        }
    };
    
    const config = defaults[type] || { port: 8000, command: '' };
    
    // Only update if fields are empty
    if (!portInput.value) {
        portInput.value = config.port;
    }
    if (!commandInput.value) {
        // Add path to command if available
        if (pathInput && config.command) {
            commandInput.value = `cd ${pathInput} && ${config.command}`;
        } else {
            commandInput.value = config.command;
        }
    }
}

function browseDirectory() {
    // Provide helpful path suggestions
    const pathInput = document.getElementById('dashboard-path');
    const homeDir = process.env.HOME || '~';
    const suggestions = [
        `${homeDir}/Projects/marketing/websites/`,
        `${homeDir}/Projects/marketing/`,
        `${homeDir}/Projects/`,
        `${homeDir}/`
    ];
    
    const suggestion = prompt(
        'Enter the full path to your project directory:\n\n' +
        'Common locations:\n' +
        suggestions.join('\n') +
        '\n\nOr paste your custom path below:',
        pathInput.value || suggestions[0]
    );
    
    if (suggestion) {
        pathInput.value = suggestion.trim();
        updateProjectTypeDefaults();
    }
}

async function saveDashboard() {
    const dashboardId = document.getElementById('dashboard-id').value;
    const path = document.getElementById('dashboard-path').value.trim();
    const name = document.getElementById('dashboard-name').value.trim();
    
    if (!path) {
        alert('Please enter a project directory path');
        return;
    }
    
    if (!name) {
        alert('Please enter a project name');
        return;
    }
    
    const data = {
        id: dashboardId || null,
        name: name,
        path: path,
        type: document.getElementById('dashboard-type').value,
        port: document.getElementById('dashboard-port').value ? parseInt(document.getElementById('dashboard-port').value) : null,
        start_command: document.getElementById('dashboard-command').value.trim() || null,
        production_url: document.getElementById('dashboard-production-url').value.trim() || null,
        api_url: document.getElementById('dashboard-api-url').value.trim() || null,
        active: document.getElementById('dashboard-active').checked
    };
    
    try {
        const endpoint = dashboardId ? '/api/dashboards/save' : '/api/dashboards/add';
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success || response.ok) {
            showNotification(
                dashboardId ? 'Dashboard updated successfully!' : 'Dashboard added successfully!',
                'success'
            );
            closeAddDashboardModal();
            
            // Reload dashboards section
            if (window.dataLoader) {
                await dataLoader.loadDashboards();
            }
        } else {
            showNotification(result.message || result.detail || 'Failed to save dashboard', 'error');
        }
    } catch (error) {
        console.error('Error saving dashboard:', error);
        showNotification('Error saving dashboard: ' + error.message, 'error');
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 px-6 py-4 rounded-lg shadow-lg transform transition-all duration-300 ${
        type === 'success' ? 'bg-green-600' :
        type === 'error' ? 'bg-red-600' :
        'bg-blue-600'
    } text-white`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Google Authentication
window.handleGoogleAuth = async function() {
    try {
        const statusResponse = await fetch('/api/auth/google/status');
        const status = await statusResponse.json();
        
        if (status.authenticated && !status.expired) {
            showNotification('✅ Already connected to Google', 'success');
            return;
        }
        
        // Open OAuth flow in popup
        const width = 500;
        const height = 600;
        const left = (screen.width - width) / 2;
        const top = (screen.height - height) / 2;
        
        const popup = window.open(
            '/auth/google',
            'GoogleAuth',
            `width=${width},height=${height},left=${left},top=${top}`
        );
        
        // Poll for popup close and check auth status
        const pollTimer = setInterval(async () => {
            if (popup.closed) {
                clearInterval(pollTimer);
                await updateGoogleAuthButton();
                showNotification('Google authentication completed!', 'success');
            }
        }, 1000);
    } catch (error) {
        console.error('Error with Google auth:', error);
        showNotification('Error connecting to Google', 'error');
    }
}

async function updateGoogleAuthButton() {
    try {
        const response = await fetch('/api/auth/google/status');
        const status = await response.json();
        
        const btn = document.getElementById('google-auth-btn');
        const text = document.getElementById('google-auth-text');
        
        if (!btn || !text) return;
        
        if (status.authenticated && !status.expired) {
            btn.className = btn.className.replace('bg-blue-600 hover:bg-blue-700', 'bg-green-600 hover:bg-green-700');
            text.textContent = '✓ Google Connected';
        } else if (status.expired) {
            btn.className = btn.className.replace('bg-blue-600 hover:bg-blue-700', 'bg-yellow-600 hover:bg-yellow-700');
            text.textContent = '⚠️ Reconnect Google';
        } else {
            btn.className = btn.className.replace('bg-green-600 hover:bg-green-700', 'bg-blue-600 hover:bg-blue-700');
            btn.className = btn.className.replace('bg-yellow-600 hover:bg-yellow-700', 'bg-blue-600 hover:bg-blue-700');
            text.textContent = 'Connect Google';
        }
    } catch (error) {
        console.error('Error updating Google auth button:', error);
    }
}

// Dismiss Vanity Alert
async function dismissAlert(alertId) {
    try {
        const response = await fetch(`/api/vanity-alerts/${alertId}/dismiss`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Alert dismissed', 'success');
            // Reload vanity alerts
            if (window.dataLoader) {
                await dataLoader.loadVanityAlerts();
            }
        } else {
            showNotification('Failed to dismiss alert', 'error');
        }
    } catch (error) {
        console.error('Error dismissing alert:', error);
        showNotification('Error dismissing alert', 'error');
    }
}

// Suggested Todos Management
async function loadSuggestedTodos() {
    try {
        const response = await fetch('/api/suggested-todos');
        const data = await response.json();
        
        if (data.success && data.suggestions && data.suggestions.length > 0) {
            renderSuggestedTodos(data.suggestions);
        } else {
            document.getElementById('suggested-todos-section').style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading suggested todos:', error);
    }
}

function renderSuggestedTodos(suggestions) {
    const section = document.getElementById('suggested-todos-section');
    const list = document.getElementById('suggested-todos-list');
    
    if (!section || !list) return;
    
    const html = suggestions.map(suggestion => {
        const sourceIcon = {
            'email': '📧',
            'calendar': '📅',
            'note': '📝',
            'default': '📌'
        }[suggestion.source] || '📌';
        
        return `
            <div class="bg-gradient-to-r from-yellow-900 to-yellow-800 rounded-lg p-4 mb-3 border border-yellow-700">
                <!-- Header with source info -->
                <div class="flex items-start justify-between gap-3 mb-3">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-lg">${sourceIcon}</span>
                            <span class="text-xs font-semibold text-yellow-200 uppercase">${escapeHtml(suggestion.source)}</span>
                            ${suggestion.priority ? `<span class="text-xs px-2 py-1 bg-yellow-700 rounded text-yellow-100">⚡ ${suggestion.priority}</span>` : ''}
                        </div>
                        <h4 class="font-bold text-white text-lg">${escapeHtml(suggestion.title)}</h4>
                        ${suggestion.description ? `<p class="text-sm text-yellow-100 mt-2">${escapeHtml(suggestion.description)}</p>` : ''}
                    </div>
                </div>
                
                <!-- Source link button -->
                ${suggestion.source_url ? `
                    <div class="mb-3">
                        <button onclick="openSourceContent('${suggestion.id}', '${suggestion.source_url}')" 
                                class="w-full px-3 py-2 bg-yellow-700 hover:bg-yellow-600 text-white text-sm rounded transition-colors"
                                title="View original source">
                            🔗 View Original ${escapeHtml(suggestion.source_title || suggestion.source)}
                        </button>
                    </div>
                ` : ''}
                
                <!-- Action buttons -->
                <div class="flex gap-2">
                    <button onclick="approveSuggestedTodo('${suggestion.id}')" 
                            class="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded transition-colors"
                            title="Add to your tasks">
                        ✓ Accept Task
                    </button>
                    <button onclick="rejectSuggestedTodo('${suggestion.id}')" 
                            class="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white font-semibold rounded transition-colors"
                            title="Dismiss this suggestion">
                        ✕ Dismiss
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    list.innerHTML = html;
    section.style.display = 'block';
}

async function approveSuggestedTodo(suggestionId) {
    try {
        const response = await fetch(`/api/suggested-todos/${suggestionId}/approve`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('✅ Task approved and added!', 'success');
            await loadSuggestedTodos();
            // Reload tasks if on that section
            if (window.dataLoader) {
                await dataLoader.loadTodos();
            }
        } else {
            showNotification('Failed to approve task', 'error');
        }
    } catch (error) {
        console.error('Error approving suggestion:', error);
        showNotification('Error approving task', 'error');
    }
}

async function rejectSuggestedTodo(suggestionId) {
    try {
        const response = await fetch(`/api/suggested-todos/${suggestionId}/reject`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('✅ Suggestion dismissed', 'success');
            await loadSuggestedTodos();
        } else {
            showNotification('Failed to dismiss suggestion', 'error');
        }
    } catch (error) {
        console.error('Error rejecting suggestion:', error);
        showNotification('Error dismissing suggestion', 'error');
    }
}

async function openSourceContent(suggestionId, sourceUrl) {
    try {
        // Create a modal to show the source content
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center modal-backdrop';
        modal.id = 'source-modal-' + suggestionId;
        
        modal.innerHTML = `
            <div class="bg-gray-900 rounded-lg w-11/12 h-5/6 flex flex-col modal-content shadow-2xl">
                <!-- Header -->
                <div class="flex items-center justify-between p-4 border-b border-gray-700">
                    <h3 class="text-xl font-bold text-white">Original Source</h3>
                    <button onclick="document.getElementById('source-modal-${suggestionId}').remove()" 
                            class="text-gray-400 hover:text-white text-2xl">✕</button>
                </div>
                <!-- Content -->
                <div class="flex-1 overflow-auto p-4 bg-gray-800">
                    <iframe src="${sourceUrl}" class="w-full h-full border-0" frameborder="0" sandbox="allow-same-origin"></iframe>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        modal.onclick = (e) => {
            if (e.target === modal) modal.remove();
        };
    } catch (error) {
        console.error('Error opening source:', error);
        showNotification('Could not open source content', 'error');
    }
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await updateGoogleAuthButton();
    await loadSuggestedTodos();
});

