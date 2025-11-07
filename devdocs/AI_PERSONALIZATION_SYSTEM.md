# AI Personalization & Training System

## Overview
Comprehensive AI training and personalization system with conversation storage, message feedback, user profiling, and continuous learning from user interactions.

## Features Implemented

### 1. User Profile System
**Purpose**: Store user information to personalize AI responses

**Database Table**: `user_profile`
- Full name, preferred name
- Occupation, company, role
- Work focus and interests
- Communication style preference
- Timezone and work hours
- Current priorities and bio

**Endpoints**:
- `GET /api/user/profile` - Retrieve user profile
- `POST /api/user/profile` - Save/update profile

**UI**: Profile modal accessible from dashboard edit panel
- Complete form for all profile fields
- Dropdown for communication style selection
- Validates and saves to database
- Used to enhance AI context in every conversation

### 2. Conversation Storage
**Purpose**: Persist all AI conversations for continuity and training

**Database Tables**:
- `ai_conversations` - Conversation metadata
- `ai_messages` - Individual messages with role and content

**Features**:
- Automatic conversation ID generation
- Messages stored with timestamps
- Conversation history retrieved for context (last 10 messages)
- User and assistant messages tracked separately

### 3. Message Feedback System
**Purpose**: Collect feedback on AI responses for quality improvement

**Database Table**: `ai_message_feedback`
- Message ID and conversation ID
- Feedback type (thumbs_up/thumbs_down)
- Optional rating (1-5)
- Optional comment

**Endpoint**: `POST /api/ai/message/feedback`

**UI**: Feedback buttons on each AI message
- 👍 Helpful button
- 👎 Not Helpful button
- Instant feedback notification
- Feedback saved for training analysis

### 4. Enhanced AI Context
**AI now receives**:
1. **User Profile Data**:
   - Name and preferred communication style
   - Role, company, work focus
   - Interests and priorities
   
2. **Dashboard Data**:
   - Active todos with priorities
   - Upcoming calendar events
   - High-priority emails
   - User feedback patterns
   
3. **Conversation History**:
   - Last 10 messages for context
   - Maintains conversation flow
   
4. **System Instructions**:
   - Explicit instruction to use provided data
   - Guidance on referencing specific items
   - Proactive assistance instructions

### 5. Background Image Feedback
**Purpose**: Learn user preferences for dashboard backgrounds

**Features**:
- 👍 Like - Saves to favorites, auto-selects from liked images
- 👎 Dislike - Fetches new image from Unsplash
- Feedback stored in localStorage
- Downloads liked images as base64
- Removes disliked images from rotation

**Methods**:
- `giveBackgroundFeedback(sentiment)` - Rate current background
- `fetchNewBackground()` - Get fresh image from Unsplash
- `downloadBackgroundImage(url)` - Save to favorites

### 6. Joke Feedback System
**Purpose**: Learn user's sense of humor

**UI**: Feedback buttons on joke card
- 👍 Thumbs up
- 👌 Neutral
- 👎 Thumbs down

**Features**:
- Auto-fetches new joke after feedback
- Stores feedback for AI training
- Reads jokes aloud with TTS
- Customizable voice for joke reading

### 7. Voice Customization
**Purpose**: Consistent voice across all dashboard TTS

**Features**:
- Voice selection dropdown in edit panel
- Test voice button
- Applies to all TTS:
  - AI chat responses
  - Calendar event alerts
  - Joke reading
  
**Methods**:
- `loadAvailableVoices()` - Get system voices
- `setAIVoice(voiceIndex)` - Select voice
- `testAIVoice()` - Preview voice
- `speakText(text)` - Use selected voice

## Data Flow

### AI Chat Request
```
User Message 
  → Load user profile from DB
  → Gather dashboard data (todos, calendar, emails)
  → Build comprehensive context
  → Include conversation history
  → Send to AI with system prompt
  → Receive response
  → Save user + AI messages to DB
  → Display with feedback buttons
  → Optionally speak response
```

### Feedback Collection
```
User Feedback (any type)
  → Save to appropriate table
  → Update personality profile
  → Trigger retraining flag
  → Update UI to reflect feedback
```

### Profile Update
```
User edits profile
  → Validate fields
  → Save to user_profile table
  → Reload profile in memory
  → Apply to next AI interaction
```

## Database Schema Updates

### New Tables
```sql
-- User profile for AI personalization
CREATE TABLE user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT,
    preferred_name TEXT,
    occupation TEXT,
    company TEXT,
    role TEXT,
    work_focus TEXT,
    interests TEXT,
    communication_style TEXT,
    timezone TEXT,
    work_hours TEXT,
    priorities TEXT,
    bio TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI message feedback
CREATE TABLE ai_message_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    rating INTEGER,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES ai_messages (id),
    FOREIGN KEY (conversation_id) REFERENCES ai_conversations (id)
);
```

### Existing Tables Used
- `ai_conversations` - Conversation metadata
- `ai_messages` - Message content
- `user_personality_profile` - Learned preferences
- `user_feedback` - General feedback on content

## API Endpoints

### User Profile
```
GET  /api/user/profile          - Get user profile
POST /api/user/profile          - Save/update profile
```

### AI Chat & Feedback
```
POST /api/ai/chat               - Send message (includes profile context)
POST /api/ai/message/feedback   - Rate AI response
GET  /api/ai/chat/conversations - List conversations
```

### Training Data
```
POST /api/ai/training/feedback  - Record item feedback
GET  /api/ai/training/summary   - Get training data summary
POST /api/ai/training/collect   - Collect training data
POST /api/ai/training/start     - Start fine-tuning
```

## Frontend State

### DashboardDataLoader Properties
```javascript
this.conversationId = null;        // Current conversation
this.userProfile = null;           // User profile data
this.aiMessages = [];              // Message history
this.selectedVoice = null;         // Chosen TTS voice
this.availableVoices = [];         // System voices
this.feedbackData = {};            // All feedback
this.backgroundImages = [];        // Background preferences
```

### LocalStorage Keys
```javascript
'taskSyncSettings'      // Task sync config
'voiceSettings'         // Selected voice
'feedbackData'          // All user feedback
'backgroundSettings'    // Background prefs
'dismissedSuggestions'  // Hidden AI suggestions
'dashboardConfig'       // Section visibility
'autoRefreshInterval'   // Refresh timing
```

## Usage Examples

### Creating User Profile
1. Click "Edit Dashboard" in sidebar
2. Scroll to "AI Personalization"
3. Click "Create Your AI Profile"
4. Fill in profile fields
5. Click "Save Profile"

### Rating AI Responses
1. Chat with AI assistant
2. See response with feedback buttons
3. Click 👍 Helpful or 👎 Not Helpful
4. Feedback saved for training

### Customizing Voice
1. Open dashboard edit panel
2. Go to "AI Voice" section
3. Select voice from dropdown
4. Click "Test Voice" to preview
5. Voice applies to all TTS

### Managing Backgrounds
1. View background image on overview
2. Click 👍 to save to favorites
3. Click 👎 to get new image
4. Liked images auto-rotate
5. Download as base64 for offline use

## Training & Learning

### Feedback Types Collected
- AI message ratings (helpful/not helpful)
- Background image preferences (like/dislike)
- Joke ratings (up/neutral/down)
- Task completion patterns
- Email priority patterns
- News article engagement

### Personality Profile
- Automatically updated based on feedback
- Groups by content type and domain
- Calculates preference scores
- Generates keywords and topics
- Saved to JSON for AI training

### Continuous Improvement
1. User interacts with dashboard
2. Gives feedback on various items
3. Feedback stored in database
4. Personality profile updated
5. AI uses profile in context
6. Responses become more personalized

## Future Enhancements
- [ ] Fine-tuning with collected feedback
- [ ] A/B testing different prompts
- [ ] Sentiment analysis on messages
- [ ] Proactive suggestions based on patterns
- [ ] Voice training with user recordings
- [ ] Multi-user profile support
- [ ] Export/import profile data
- [ ] Analytics dashboard for feedback

## Technical Notes

### User Profile Integration
The user profile is loaded on dashboard init and included in every AI chat request:
```javascript
// In sendAIMessage()
const context = {
  current_time: new Date().toLocaleString(),
  todos: {...},
  calendar: {...},
  emails: {...},
  user_preferences: {...}
};
```

### Conversation Continuity
Conversation ID persists across messages in same session:
```javascript
// First message creates conversation
if (!conversation_id) {
  conversation_id = `conv_${timestamp}`;
}
// Subsequent messages use same ID
this.conversationId = data.conversation_id;
```

### Voice Consistency
Selected voice stored and applied to all TTS:
```javascript
speakText(text) {
  const utterance = new SpeechSynthesisUtterance(text);
  if (this.selectedVoice) {
    utterance.voice = this.availableVoices[this.selectedVoice];
  }
  this.speechSynthesis.speak(utterance);
}
```

## Testing Checklist
- [ ] Create user profile and verify save
- [ ] Chat with AI and check context includes profile
- [ ] Rate AI messages with thumbs up/down
- [ ] Change voice and test across features
- [ ] Like/dislike background images
- [ ] Rate jokes and verify new joke loads
- [ ] Check conversation persistence across messages
- [ ] Verify feedback saved to database
- [ ] Test voice works for chat, alerts, and jokes
- [ ] Confirm profile updates apply immediately

## Conclusion
This system creates a comprehensive feedback loop where:
1. User provides information via profile
2. AI uses profile for personalized responses
3. User rates responses and content
4. Feedback improves future interactions
5. System learns preferences over time
6. Dashboard becomes increasingly personalized

The result is an AI assistant that truly knows the user and adapts to their preferences, communication style, and priorities.
