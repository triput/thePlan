# **Product Specification & Architecture Document**

**Project:** Modern Automated Productivity Application (Web-First Task & Scheduling Engine)  
**Version:** 1.0  
**Status:** Draft Architecture & Database Design Specification

## **1\. Core Product Vision & Objectives**

This document defines the product requirements and technical architecture for a web-first, high-performance productivity application designed to bridge the gap between structured task management (inspired by Todoist) and automated, dynamic time-blocking (inspired by Skedpal). The application prioritizes high execution speed, deep hierarchical task organization, and dynamic calendar allocation without gamification fluff.

### **Key Principles**

> * **Speed First:** Instant UI responsiveness (sub-100ms interaction latency) using client-side caching and optimistic rendering.  
> * **Utility Over Gamification:** Focus purely on clean tracking, focus windows, and execution. Zero karma scores or streak badges.  
> * **Expanded Structure:** Extends traditional task organization by introducing a top-level Epic layer and an extra subtask depth layer beyond standard task tools.  
> * **Dynamic Scheduling:** Flexible time-blocking using fuzzy logic to dynamically fit tasks around fixed external calendar commitments.  
> * **Local & Secure Infrastructure:** Containerized execution on local hardware with secure external tunneling via Cloudflare Tunnels and PostgreSQL database architecture.

## **2\. Information Architecture & Hierarchy**

The application's structural model expands traditional task layers to accommodate multi-month initiative planning alongside fine-grained task execution:  
**Epic** (Top-Level Container) → **Project / Category** → **Section** → **Parent Task** → **Subtask** → **Nested Subtask (Deep Layer)**

| Level | Scope & Description | Key Attributes   |
| :---- | :---- | :---- |
| **Epic** | Strategic initiatives spanning multiple projects or months. | Title, Target Date, Color, Status, Aggregated Time Estimates. |
| **Project** | Functional domains or broad goal categories. | Color Palette (Custom & Standard), Views, Archive State. |
| **Section** | Visual grouping within a project. | Sort Order, Project ID. |
| **Task & Deep Subtasks** | Actionable work units supporting two levels of subtask nesting. | Duration, Priority (P1-P4), Min/Max Slices, Dependencies, Time Windows. |

## **3\. System Architecture & Decisions**

Based on strategic review, the following technical choices govern the core system implementation:

> * **Database Layer:** PostgreSQL managed via containerized Podman engine, utilizing Alembic migration scripts. This maintains local sovereignty and instant performance while allowing easy transition to hosted PostgreSQL if required.  
> * **Security & External Access:** Remote access is mediated through **Cloudflare Tunnels** rather than manual router port forwarding, eliminating open external ports and securing traffic with automated TLS certificates and edge authentication.  
> * **Engine Decoupling:** Core task management CRUD and client UI interactions are strictly isolated from the auto-scheduling engine. The system functions at peak speed even during background recalculations or offline states.  
> * **Client-Side Performance:** Optimistic rendering on the web client provides immediate local updates, syncing asynchronously with the backend database.

## **4\. Relational PostgreSQL Database Schema**

The database design utilizes PostgreSQL with strict referential integrity, indexing optimized for quick hierarchy lookups, and support for complex scheduling attributes.

`-- Enable UUID extension`  
`CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`

`-- Enum types for priority, scheduling state, and external calendar sync status`  
`CREATE TYPE task_priority AS ENUM ('p1', 'p2', 'p3', 'p4');`  
`CREATE TYPE schedule_status AS ENUM ('unscheduled', 'scheduled', 'pinned', 'completed', 'cancelled');`  
`CREATE TYPE calendar_provider AS ENUM ('google', 'microsoft');`

`-- 1. EPICS TABLE`  
`CREATE TABLE epics (`  
    `id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),`  
    `title VARCHAR(255) NOT NULL,`  
    `description TEXT,`  
    `color_hex VARCHAR(7) DEFAULT '#3B82F6',`  
    `start_date DATE,`  
    `target_date DATE,`  
    `is_archived BOOLEAN DEFAULT FALSE,`  
    `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,`  
    `updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`  
`);`

`-- 2. PROJECTS TABLE`  
`CREATE TABLE projects (`  
    `id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),`  
    `epic_id UUID REFERENCES epics(id) ON DELETE SET NULL,`  
    `title VARCHAR(255) NOT NULL,`  
    `description TEXT,`  
    `color_hex VARCHAR(7) DEFAULT '#10B981',`  
    `sort_order INT DEFAULT 0,`  
    `is_archived BOOLEAN DEFAULT FALSE,`  
    `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,`  
    `updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`  
`);`

`-- 3. SECTIONS TABLE`  
`CREATE TABLE sections (`  
    `id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),`  
    `project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,`  
    `title VARCHAR(255) NOT NULL,`  
    `sort_order INT DEFAULT 0,`  
    `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`  
`);`

`-- 4. TASKS TABLE (Supports multi-level subtask nesting & Skedpal scheduling metadata)`  
`CREATE TABLE tasks (`  
    `id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),`  
    `project_id UUID REFERENCES projects(id) ON DELETE CASCADE,`  
    `section_id UUID REFERENCES sections(id) ON DELETE SET NULL,`  
    `parent_task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,`  
      
    `title VARCHAR(500) NOT NULL,`  
    `description TEXT,`  
    `priority task_priority DEFAULT 'p4',`  
      
    `-- Nesting & Hierarchy Tracking`  
    `nesting_level INT NOT NULL DEFAULT 0 CHECK (nesting_level <= 2), -- 0=Parent, 1=Subtask, 2=Nested Subtask`  
    `sort_order INT DEFAULT 0,`  
      
    `-- Time Estimation & Scheduling Metadata (Skedpal Engine)`  
    `estimated_duration_minutes INT DEFAULT 30,`  
    `min_block_duration_minutes INT DEFAULT 15,`  
    `max_block_duration_minutes INT DEFAULT 120,`  
      
    `due_date TIMESTAMP WITH TIME ZONE,`  
    `soft_target_date TIMESTAMP WITH TIME ZONE,`  
    `preferred_time_window VARCHAR(100), -- e.g., "Morning Deep Work", "Afternoon Admin"`  
      
    `status schedule_status DEFAULT 'unscheduled',`  
    `is_completed BOOLEAN DEFAULT FALSE,`  
    `completed_at TIMESTAMP WITH TIME ZONE,`  
      
    `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,`  
    `updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`  
`);`

`-- 5. TASK DEPENDENCIES TABLE`  
`CREATE TABLE task_dependencies (`  
    `id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),`  
    `blocking_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,`  
    `dependent_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,`  
    `CONSTRAINT unique_dependency UNIQUE(blocking_task_id, dependent_task_id),`  
    `CONSTRAINT no_self_dependency CHECK (blocking_task_id != dependent_task_id)`  
`);`

`-- 6. SCHEDULED TIME BLOCKS TABLE (Output of Skedpal Fuzzy Scheduler)`  
`CREATE TABLE scheduled_blocks (`  
    `id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),`  
    `task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,`  
    `start_time TIMESTAMP WITH TIME ZONE NOT NULL,`  
    `end_time TIMESTAMP WITH TIME ZONE NOT NULL,`  
    `is_pinned BOOLEAN DEFAULT FALSE, -- Pinned blocks resist auto-rescheduling`  
    `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,`  
    `updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`  
`);`

`-- 7. EXTERNAL CALENDAR SYNC TABLE`  
`CREATE TABLE external_calendar_events (`  
    `id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),`  
    `task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,`  
    `scheduled_block_id UUID REFERENCES scheduled_blocks(id) ON DELETE SET NULL,`  
    `provider calendar_provider NOT NULL,`  
    `external_event_id VARCHAR(255) NOT NULL,`  
    `calendar_id VARCHAR(255) NOT NULL,`  
    `sync_hash VARCHAR(64),`  
    `last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,`  
    `CONSTRAINT unique_external_event UNIQUE(provider, external_event_id)`  
`);`

`-- INDEXES FOR HIGH-SPEED QUERY PERFORMANCE`  
`CREATE INDEX idx_projects_epic ON projects(epic_id);`  
`CREATE INDEX idx_tasks_project ON tasks(project_id);`  
`CREATE INDEX idx_tasks_parent ON tasks(parent_task_id);`  
`CREATE INDEX idx_tasks_nesting ON tasks(nesting_level);`  
`CREATE INDEX idx_scheduled_blocks_task ON scheduled_blocks(task_id);`  
`CREATE INDEX idx_scheduled_blocks_time ON scheduled_blocks(start_time, end_time);`

## **5\. Phased Implementation Roadmap**

| Phase | Focus & Scope | Key Deliverables   |
| :---- | :---- | :---- |
| **Phase 1: MVP** | Core Task Management & High-Speed Web Interface. | Epics, Projects, Sections, Nested Tasks, Basic Natural Language Quick-Add, Cloudflare Tunnel deployment. |
| **Phase 2: Auto-Scheduler** | Dynamic Time-Blocking & Calendar Integration. | Skedpal-style fuzzy logic scheduling engine, Bidirectional Google Calendar sync, Task dependency resolution. |
| **Phase 3: SLM & Desktop** | Intelligence Layer & Native Clients. | Local Small Language Model integration (Ollama/vLLM) for advanced parsing/scheduling, Microsoft Calendar sync, Native desktop application. |

## **Architectural Summary: Dual-Layer Time Processing Model**

To keep the application mathematically sound for scheduling algorithms while ensuring zero cognitive friction for users, the architecture decouples **Internal Calculation Storage** from **User Inputs and UI Reporting**.

                    ┌──────────────────────────────────────────┐  
                     │           User Input (Quick Add)         │  
                     │  "Write report 1.5h due next Tue at 3pm" │  
                     └────────────────────┬─────────────────────┘  
                                          │  
                                          ▼  
                     ┌──────────────────────────────────────────┐  
                     │      Natural Language Parsing Engine     │  
                     └────────────────────┬─────────────────────┘  
                                          │  
                                          ▼  
 ┌─────────────────────────────────────────────────────────────────────────────────┐  
 │                           Internal Database Storage                             │  
 │  • Base Minutes: estimated\_duration\_minutes \= 90                                │  
 │  • Target Timestamp: due\_date \= 2026-08-11T15:00:00Z (ISO-8601 UTC)             │  
 └────────────────────────────────────────┬────────────────────────────────────────┘  
                                          │  
                                          ▼  
                     ┌──────────────────────────────────────────┐  
                     │        UI Visual Reporting Formatter     │  
                     └────────────────────┬─────────────────────┘  
                                          │  
                                          ▼  
 ┌─────────────────────────────────────────────────────────────────────────────────┐  
 │                            User Interface Render                                │  
 │  • Task View: "1h 30m"                                                          │  
 │  • Project Aggregate: "3.5 days left"                                           │  
 │  • Epic Rollup: "2.5 months effort remaining"                                   │  
 └─────────────────────────────────────────────────────────────────────────────────┘

### **Key Functional Specifications**

1. **Input Parsing Rules:**  
   * **Durations:** Supports explicit unit syntax during task capture (e.g., 45m, 1.5h, 2d, 3w, 1.5m for months, 1y).  
   * **Timestamps & Dates:** Parses relative phrases (tomorrow at 2pm, next Thursday, end of next month) directly into absolute ISO-8601 UTC timestamps.  
2. **Configurable Work Capacity Baselines:**  
   * For dynamic task auto-scheduling, multi-day duration estimates translate into working capacity rather than 24-hour elapsed time:  
     * **1 Work Day** \= 8 Working Hours (480 minutes)  
     * **1 Work Week** \= 5 Work Days / 40 Working Hours (2,400 minutes)  
     * **1 Work Month** \= 20 Work Days / 160 Working Hours (9,600 minutes)  
3. **Dynamic Scale-Aware UI Formatting:**  
   * The visual renderer checks the calculated minute total or date distance and presents the unit best suited to the view scale:  
     * **\< 60 Minutes:** Rendered as minutes (45m).  
     * **1 to 24 Hours:** Rendered as hours and minutes (2h 30m).  
     * **1 to 30 Days:** Rendered as days (3.5 days).  
     * **1 to 12 Months:** Rendered as fractional months (2.5 months).  
     * **\> 12 Months:** Rendered as fractional years (1.2 years effort).

# **Algorithmic Specification: Dynamic Scheduling Engine**

The auto-scheduling engine runs as a decoupled, asynchronous background pipeline. It converts unscheduled tasks, duration estimates, dependencies, and time windows into non-overlapping scheduled\_blocks overlaid onto external calendar availability.

┌─────────────────────────────────────────────────────────────────────────────────┐  
│                        Phase 1: Calendar Busy Map Generation                     │  
│  External GCal/MSCal Events \+ Pinned Blocks ──► Continuous BUSY / FREE Timeline │  
└────────────────────────────────────────┬────────────────────────────────────────┘  
                                         │  
                                         ▼  
┌─────────────────────────────────────────────────────────────────────────────────┐  
│                    Phase 2: Topological Dependency Resolution                    │  
│  Task Dependency Graph (DAG) ──► Strict Precedence Execution Order              │  
└────────────────────────────────────────┬────────────────────────────────────────┘  
                                         │  
                                         ▼  
┌─────────────────────────────────────────────────────────────────────────────────┐  
│                     Phase 3: Priority Scoring & Rank Queue                       │  
│  Calculate Dynamic UPS Score ──► Sorted Candidate Task Queue                    │  
└────────────────────────────────────────┬────────────────────────────────────────┘  
                                         │  
                                         ▼  
┌─────────────────────────────────────────────────────────────────────────────────┐  
│                   Phase 4: Slicing & Fuzzy Allocation Pass                      │  
│  Min/Max Slices ──► Time Window Matching ──► Soft Block Allocation               │  
└────────────────────────────────────────┬────────────────────────────────────────┘  
                                         │  
                                         ▼  
┌─────────────────────────────────────────────────────────────────────────────────┐  
│                    Phase 5: Conflict Handling & Overbooking                      │  
│  Slack \< 0 ──► Window Relaxation / Flag Overbooked ──► Preserve Pinned Integrity│  
└─────────────────────────────────────────────────────────────────────────────────┘

## **1\. Step-by-Step Scheduling Pipeline**

### **Phase 1: Calendar Cutout & Busy Map Construction**

1. Fetch all hard events from external calendars (Google Calendar / Microsoft Calendar) and internal scheduled\_blocks marked as is\_pinned \= TRUE across the target scheduling horizon.  
2. Overlay user-configured time windows (e.g., *Working Hours: Mon-Fri 08:00–17:00*, *Morning Deep Work: 08:00–11:00*).  
3. Construct a temporal availability timeline where time slots are categorized as BUSY (hard block), RESERVED (pinned task block), or FREE (open for allocation).

### **Phase 2: Topological Dependency Resolution**

1. Construct a Directed Acyclic Graph (DAG) using the task\_dependencies table.  
2. Perform a topological sort to establish strict execution ordering.  
3. Assign early-start constraint bounds: a dependent task cannot be scheduled prior to the estimated completion timestamp of all its prerequisite tasks.

### **Phase 3: Priority Scoring & Rank Queue Generation**

1. Calculate a dynamic **Urgency & Priority Score (UPS)** for every unscheduled task.  
2. Insert candidate tasks into a max-priority queue sorted in descending order by UPS.

### **Phase 4: Task Slicing & Fuzzy Allocation Pass**

For each task in the max-priority queue:

1. **Determine Slice Constraints:** Retrieve estimated\_duration\_minutes, min\_block\_duration\_minutes, and max\_block\_duration\_minutes.  
2. **Filter Feasible Windows:** Search the availability map for FREE slots that match the task's preferred\_time\_window between CURRENT\_TIMESTAMP and due\_date.  
3. **Slice & Fit Algorithm:**  
   * If an available contiguous FREE block $\\ge \\text{estimated\\\_duration\\\_minutes}$, allocate a single scheduled\_block.  
   * If contiguous free space is smaller than total duration but $\\ge \\text{min\\\_block\\\_duration\\\_minutes}$, split the task into multiple execution slices bounded by max\_block\_duration\_minutes until total duration is satisfied.  
4. Update the availability map by marking allocated slots as SOFT\_SCHEDULED.

### **Phase 5: Conflict Resolution & Overbooking Handling**

1. **Slack Depletion Warning:** If a task's calculated completion time exceeds its due\_date, trigger a fuzzy relaxation pass.  
2. **Fuzzy Window Relaxation:** Relax preferred\_time\_window constraints (e.g., allowing an "Afternoon Work" window to utilize general "Working Hours") to fit the task.  
3. **Overbook Handling:** If a task cannot fit before its hard deadline without violating higher-priority or pinned tasks, flag its status as OVERBOOKED in the UI. Pinned blocks and higher-priority tasks are never altered automatically.

## **2\. Priority Scoring Formula (UPS)**

The Dynamic Urgency & Priority Score (UPS) balances explicit user priority, deadline proximity, dependency impact, and top-level initiative alignment:

$$\\text{UPS} \= (W\_p \\cdot P) \+ (W\_u \\cdot U) \+ (W\_d \\cdot D) \+ (W\_e \\cdot E)$$

| Parameter | Symbol | Definition & Formula | Weight (W) |
| :---- | :---- | :---- | :---- |
| **Base Priority** | $P$ | Numeric value mapped directly from explicit user settings: **P1 \= 100**, **P2 \= 75**, **P3 \= 50**, **P4 \= 25**. | $W\_p \= 0.35$ |
| **Dynamic Urgency** | $U$ | Exponential scale based on remaining slack time: $$\\text{Slack} \= \\frac{\\text{DueDate} \- \\text{CurrentTime} \- \\text{RemainingDuration}}{\\text{RemainingDuration}}$$ When $\\text{Slack} \\le 0$, $U \= 100$. As slack grows, $U$ decays rapidly. | $W\_u \= 0.40$ |
| **Dependency Depth** | $D$ | Count of downstream tasks directly or indirectly blocked by this task ($0$ to $100$ normalized scale). | $W\_d \= 0.15$ |
| **Epic Alignment** | $E$ | Weight boosted if the parent Epic has a near-term target date ($0$ or $100$). | $W\_e \= 0.10$ |

## **3\. Fuzzy Time-Blocking Rules**

1. **Contiguity Optimization:** The scheduler prefers placing task slices in contiguous back-to-back blocks within a focus window rather than fragmenting work into scattered minimum slices.  
2. **Buffer Rules:** Every auto-scheduled block automatically inserts a non-configurable 5-minute buffer between back-to-back task slices to prevent focus fatigue.  
3. **Reschedule Stability (Pinning):**  
   * Users can manually move or lock any auto-scheduled block on the calendar view, toggling is\_pinned \= TRUE.  
   * The scheduler treats pinned blocks as hard calendar events, re-running fuzzy logic strictly around them.

# **Quick-Add Natural Language Parser Architecture**

The parser operates as a deterministic, multi-pass pipeline. It scans the incoming raw string, identifies syntax patterns using a strict rule hierarchy, extracts metadata into strongly typed structures, and strips the metadata tokens to leave behind a clean task title.

                  ┌─────────────────────────────────────────┐  
                   │    Raw Input String (Quick-Add Box)     │  
                   │ "Draft spec 1.5h p1 \!\!Epic:Organon \#Dev"│  
                   └────────────────────┬────────────────────┘  
                                        │  
                                        ▼  
                   ┌─────────────────────────────────────────┐  
                   │     Pass 1: Tokenizer & Lexer           │  
                   │ (Delimiters, Quotes, Metadata Tags)     │  
                   └────────────────────┬────────────────────┘  
                                        │  
                                        ▼  
                   ┌─────────────────────────────────────────┐  
                   │ Phase 2: Metadata Extraction Pipeline   │  
                   │  1\. Explicit Tags (\!\!Epic, \#Project)    │  
                   │  2\. Priority Tokens (p1, p2, \!p1)       │  
                   │  3\. Duration Strings (1.5h, 45m, 2d)    │  
                   │  4\. Date/Time Expression Engine        │  
                   └────────────────────┬────────────────────┘  
                                        │  
                                        ▼  
                   ┌─────────────────────────────────────────┐  
                   │ Pass 3: Title Sanitization & Stripping  │  
                   │ (Remove metadata tokens, normalize space)│  
                   └────────────────────┬────────────────────┘  
                                        │  
                                        ▼  
                   ┌─────────────────────────────────────────┐  
                   │   Parsed Structured Task Object Output  │  
                   └─────────────────────────────────────────┘

## **1\. Rule Precedence Hierarchy**

To resolve syntax ambiguity (e.g., distinguishing whether "p1" means Priority 1 or part of "p10", or whether "in 2 days" is a date or a duration), tokens are extracted in a strict precedence order:

1. **Explicit Tag Markers (\!\! and \#):** High-confidence, non-ambiguous tags.  
2. **Explicit Priority Markers (p1–p4, \!p1–\!p4):** Fixed enumeration matching.  
3. **Explicit Duration Units (1.5h, 45m, 2w):** Numeric-plus-unit strings.  
4. **Relative / Absolute Date Expressions:** Date and time window resolution.  
5. **Title Fallback:** Remaining unparsed string tokens.

## **2\. Token Extraction Rules & Logic**

### **Pass 1: Epic and Project Tag Extraction**

Explicit prefix markers take immediate priority to prevent tag names from colliding with date/duration keywords.

* **Epic Prefix (\!\! or epic:):**  
  * *Pattern:* (?:\!\!|epic:)(?:"(\[^"\]+)"|'(\[^'\]+)'|(\\S+))  
  * *Examples:* \!\!Organon, \!\!"Q3 Infrastructure", epic:Auth  
  * *Behavior:* Matches either quoted multi-word strings or unquoted contiguous characters. Matches are linked to the corresponding epic\_id.  
* **Project Prefix (\#):**  
  * *Pattern:* \#(?:"(\[^"\]+)"|'(\[^'\]+)'|(\\S+))  
  * *Examples:* \#CoreEngine, \#"Client App"  
  * *Behavior:* Links the task to the designated project. If a section is included via / (e.g., \#CoreEngine/Backend), it resolves both project and section.

### **Pass 2: Priority Extraction**

Priority tokens are parsed using explicit boundaries to avoid matching inside standard words (like "apple" or "map1").

* *Pattern:* (?\<=\\s|^)(?:p|P|\!)(1|2|3|4)(?=\\s|$)  
* *Mapping:*  
  * p1 / \!1 / P1 $\\rightarrow$ task\_priority.p1 (Highest)  
  * p2 / \!2 / P2 $\\rightarrow$ task\_priority.p2  
  * p3 / \!3 / P3 $\\rightarrow$ task\_priority.p3  
  * p4 / \!4 / P4 $\\rightarrow$ task\_priority.p4 (Default)

### **Pass 3: Duration Extraction**

Durations are converted directly into integer base minutes for internal database storage.

* *Pattern:* (?\<=\\s|^)(\\d+(?:\\.\\d+)?)\\s\*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|mo|mon|mth|month|months|y|yr|yrs|year|years)(?=\\s|$)  
* *Conversion Logic:*  
  * m / mins: value \* 1  
  * h / hrs: value \* 60  
  * d / days: value \* 480 (8-hour work capacity baseline)  
  * w / weeks: value \* 2,400 (40-hour work capacity baseline)  
  * mo / months: value \* 9,600 (160-hour work capacity baseline)  
  * y / years: value \* 115,200 (1,920-hour work capacity baseline)

### **Pass 4: Date & Time Window Resolution**

Date parsing operates on relative offsets, absolute calendar dates, and fuzzy time windows.

1. **Relative Date Phrases:**  
   * *Keywords:* today, tomorrow (tom), yesterday, next (monday|tue|wed|...)  
   * *Logic:* Computes target date relative to the user's current local timezone date boundary.  
2. **Absolute Date Expressions:**  
   * *Formats:* YYYY-MM-DD, MM/DD/YYYY, DD-MMM (e.g., 15-Aug, Oct 24)  
   * *Logic:* Converts directly to ISO-8601 UTC timestamp based on user local offset.  
3. **Explicit Time & Time-Window Bounds:**  
   * *Exact Time:* at 3pm, at 14:30 $\\rightarrow$ Binds the specific target execution timestamp.  
   * *Fuzzy Windows:* @morning (08:00–12:00), @afternoon (12:00–17:00), @evening (17:00–21:00) $\\rightarrow$ Populates the preferred\_time\_window field for the Skedpal engine.

## **3\. Title Sanitization Pass**

Once metadata tokens are successfully extracted and assigned to the structured task payload, the parser executes a cleanup sweep:

1. Strips all matched token character ranges from the raw string.  
2. Collapses multi-space whitespace into single spaces.  
3. Trims leading and trailing punctuation/spaces.  
4. Returns the clean remainder string as the task title.

## **4\. Example Parsing Walkthrough**

**Input String:**

> "Review architecture spec 1.5h p1 next Tue at 9am \!\!Organon \#Dev/Backend @morning"

**Extraction Results:**

* **Epic:** Organon (from \!\!Organon)  
* **Project / Section:** Dev / Backend (from \#Dev/Backend)  
* **Priority:** p1 (from p1)  
* **Duration:** 90 minutes (from 1.5h)  
* **Due Date:** 2026-08-11T09:00:00 (calculated from next Tue at 9am relative to current date)  
* **Preferred Window:** morning (from @morning)  
* **Sanitized Title:** "Review architecture spec"

