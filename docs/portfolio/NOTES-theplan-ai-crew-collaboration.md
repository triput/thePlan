# thePlan, with a crew

**Thesis:** I design and direct a local-first household scheduler with an AI crew, and the part I will defend in an interview is Julie: a local model that proposes and waits, a CLI an agent can actually script, and a field test that refuses to call saved configuration a placed block.

**Draft:** 2026-10-12, for interviews and a later GitHub show-and-tell. Read the living footnote before you quote numbers, stamps, or "shipped" out loud.

**Technical briefing map (Page):** [THEPLAN-SPEAKABLE-OVERVIEW.md](./THEPLAN-SPEAKABLE-OVERVIEW.md) — architecture and do-not-claim; this essay is the narrative.

---

## What it is

thePlan is the planner I run at home. One person per account, more than one account on the same stack if the household needs it, no team workspace and no streak badges. The job is the boring one that matters: capture work, keep a deep hierarchy (epic, project, section, task, and a couple of subtask levels), see a calendar, and time-block without turning my life into a game.

It is local-first on purpose. Docker Compose, a FastAPI service, Postgres on the machine I control, a Vite/React client in front. A tunnel is how a phone reaches that machine. Task data stays on the home host.

The tracked tree is a real application, on the order of seventy-seven thousand lines of code: about fifty-one thousand Python, sixteen thousand TSX, five thousand TypeScript, four thousand CSS, inside a larger pile of tracked text closer to a hundred thousand. Recount before you say that in a room. The point of the number is scale. This is a scheduler with ownership rules, migrations, and a worker, maintained as a product.

Scheduling is the long bet. Fuzzy time-blocking is in the bones of the product. The 0.7 pass is the grown-up settings layer: availability, effort, and an honest read of what the placer is actually using. As of this draft, those foundations are in progress on the household stack. I will not call 0.7 finished here. See the footnote.

## How I work with the crew

I do not claim the commits as solo handwriting. That would be a lie, and it would also hide the skill I want hired for.

The hats I will say out loud: designer, TPM, director of development, product owner. I pick the behavior from lived examples. I set the gates. I read the code, the diffs, and the records. Vibes are a brainstorm. They are a terrible release gate.

The crew has names because the work has seats. Steve keeps the phases in order so nobody skips from "it compiles" to a victory lap. Jules takes the architecture that has to hold. Tesla takes the sharp edges: auth, data, anything that fails in interesting ways at the boundary. Andi builds UI once the behavior is tight enough to specify. Renee decides what a green suite actually proved, and keeps automated checks distinct from a human pass. Page writes the record so later-me cannot gaslight present-me. Drew audits dates and claims before they leave the building. Dex reviews delivered behavior against the decision I approved, and he is not shy when the words and the code diverge. Reed writes sentences like these.

A slice is not closed because a builder is proud of it. Quality exits first. If the tests are still red, the paper stays open. I would rather say "in progress" in an interview than walk back a stamp.

## Julie, and the AI access I will actually demo

Julie is a first-class way to use thePlan. She is the agent I hand real workflows: read the account, propose a structure, stop for me, apply only what I approved, and field-test scheduling foundations without touching my live coursework. If the only AI story I had was "the crew wrote the app," I would be describing a staffing model. Julie is a product surface.

### Assist: the model proposes, then it waits

Assist is optional, local, and rude about consent. I type what I want. thePlan asks a model on the home machine, default Ollama, for a structured action list. I get a review. I edit or delete rows. I approve. Then apply runs through the same ownership rules as ordinary create-task and create-project. The model does not write the database. There is no auto-apply, and I do not want one.

The browser never talks to Ollama. Phone or laptop hits the API, through the tunnel when I am away. The API talks to Ollama on the same host. Remote Assist needs those two to see each other. It does not need the model exposed on the internet. If Ollama is down, Assist fails soft and says so. Inbox, calendar, and ordinary CRUD keep working. A planner that bricks because a local model took a nap is a toy.

The honesty cut is the part I will slow down for. When the sentence has a parseable due or duration, the deterministic quick-add parser owns those fields. Assist prefers the parser over the model's guess. "At 9pm," "at 21:00," "for an hour," "duration 60 minutes": those are parsed, then shown on the review row as editable values. Empty duration falls back to the settings default only after I have seen the row. "Schedule at ..." in this cut means a task due and an estimate. It does not mean a calendar block. I like that the product says the narrower thing.

Quick-add stays the fast path when I already know the shape of the task. Assist is how a sentence becomes a reviewable list: `create_task` and `create_project` in scope, deletes and schedule mutations left out. The CLI speaks the same contract. `theplan assist propose` returns the list. `theplan assist apply` commits the file I hand it. Propose is a question. Apply is the decision.

`theplan status` is a small tell I like. Health and who-am-I come back, and Assist reachability rides along inside the JSON. If the model is unhappy, that fact stays in the payload. The command can still exit clean when the API itself is fine. The app knows the difference between "I am down" and "the sidekick is down."

### The CLI is the agent door

The CLI is how an agent operates the product without scraping a webpage or guessing at prose. Default output is one JSON object. Failures use a stable code and an exit status: usage, auth, not found, unavailable, conflict. Scripts can branch. Agents are told to skip interactive prompts.

That surface is wide enough to be a daily driver for Julie, on purpose. Login and a session file. Tasks. Hierarchy: epics, projects, sections, dependencies. Assist propose and apply. Planning handoff with an idempotency key and a receipt you can look up if the response gets lost. Templates for course-shaped JSON, same propose-then-apply shape, same "keep the key, do not mint a new one because you got nervous" rule. Saved views. And, for the 0.7 foundations, settings, availability, progress, and a read-only "what is actually effective" query.

Handoff is the path for an agreed plan: propose a graph, I look, apply once, replay the receipt. Outline import is the sibling for curriculum JSON, and it is a different promise. I say both out loud so nobody treats them as the same button.

### Outlines and course import

A syllabus should not become four hundred hand-typed tasks, and it should not become a Coursera client hiding inside my planner. Outline ingest is deterministic. No model required. Paste or upload JSON, or send it through the template commands. Propose builds a tree. I skim, drop rows, skip optional items if I mean to. Approve writes epic, projects, sections, and tasks under my account, with labels from the task type.

The mapping is dull in the way I trust. A certificate is an epic. A course is a project. A module is a section. A lesson, reading, quiz, or lab is a task. Durations come from the outline when the outline has them. The product does not invent due dates because a module happened to be week three. It does not log into Coursera, scrape progress, or sync grades. If I want a curriculum in, I bring JSON I can read.

The contract fixture is a full professional-certificate outline, on the order of ten courses, thirty modules, and 417 tasks. That is the scale the path was built to survive. Re-import still duplicates. I will say that before anyone calls it magic. Dedupe is backlog, and pretending otherwise is how you get two of every lab.

Julie's course guide is the human version of the same gate. Confirm the account. Capture the real syllabus. Build the outline. Propose. Show me destination, counts, estimates that were supplied versus defaulted, and the scheduling policy. Templates propose a manual policy in the current cut. If I want the scheduler involved, that is a separate agreement. Apply uses a key I saved first. If the call times out, look up the receipt. Same proposal, same key. Verify with read-back. The first course we aimed at her was a Kubernetes syllabus I had not started, so the guide assumes uncompleted work and tells her not to invent a curriculum she could not see. I am not claiming that import already landed. The workflow is real. The footnote can say whether a specific course has.

### She field-tested the scheduling foundations

On 12 October 2026 Julie ran a bounded CLI acceptance pass against a frozen build, on a disposable account walled off from household data. Eleven checks, eleven passes. Dex recorded the result. Full scheduling acceptance is a different claim, and the checklist says so in the first screen. I trust it more because of that sentence.

What she was asked to prove is the part I want a hiring manager to hear.

Saving General or Working availability in this slice stores configuration. The read-back says it is not scheduling-effective yet. The placer still follows the older time-map and workweek path. A Monday-through-Friday, same-hours Working edit can mirror into those legacy settings. A Tuesday-through-Saturday pattern must not silently rewrite them. Julie checked the shifted week and the legacy hours stayed put. That is the test: the new drawer does not get to lie about the old engine.

Effort is three numbers, and they are allowed to disagree. Original estimate, time worked, remaining estimate. A 120-minute task starts at 120, 0, 120. Log 20 minutes worked and confirm 90 remaining, and you get 120, 20, 90. Remaining is outstanding work, free to disagree with original minus worked. Replay the same progress action and it must not count twice. Set remaining to zero and the task stays open. Completion is a separate decision. A stale scheduling revision is rejected. You refresh and reconsider. You do not retry an old decision with a newer token and hope.

The last check asks the product to distinguish inputs the placer is using now from configuration that is saved and still inactive. Julie had to see that difference in the output. I care about that more than a demo where a model cheerfully "schedules my week" and nobody can say from which rules.

She did this through the CLI, in JSON and in text, on an account that was allowed to be disposable. Awkward successes were in scope as usability notes. That is what I mean by field tester. A persona in a slide does not restore settings afterward.

Later, for her, is the actual adventure: placement, May/Must/Prefer, contexts, pins, chunking, Assist-driven setup. This pass did not require a replan. I will not narrate those as done.

## What I will put on the table

If you give me a laptop and ten minutes, this is the order.

1. **Assist, slowly.** A sentence with a clock time. Propose. The review row shows a due and a duration I can edit. I point at the rule: if the sentence was parseable, the parser won, and the model did not get to freelance the timestamp. I do not hit approve unless I mean to leave a task behind.

2. **The sidekick can be down.** `theplan status`, and the Assist block inside an otherwise healthy response. Then one sentence on topology: the phone talks to my API, and the API talks to Ollama on the home host.

3. **An agent door with a receipt.** A template or handoff propose that prints a tree and stops. I say apply is a second command, with a key I already wrote down. I mention that outline re-import will duplicate until we build dedupe, because I would rather spoil the trick than get caught by it.

4. **Julie's eleven.** The result line, then the limitation in the same breath. She passed a foundations checklist on a frozen build. Availability she saved is configuration. Placement is still the older path. Remaining effort is not "original minus worked" unless I say so. Zero remaining does not complete the task. I can open the checklist if someone wants the rows.

5. **A gate with my name on it.** An ADR or a delivery note where I accepted a slice and refused a bigger stamp. The 0.7 work is the current example: foundations I will walk through, a cutover I will not cosplay as finished. I read that code. I did not type all of it. Both sentences belong in the room.

What I am proud of is the combination. A crew can build faster than I can type, and the product still has a human hand on apply, a local model with a narrow vocabulary, an agent who can run a checklist, and records that distinguish "saved" from "in force." That is the job I do. Director, in the literal sense: I direct.

## If this becomes a talk

- Open on Julie's checklist. Eleven passes, and the first thing the doc admits is what the pass leaves for later.
- One diagram, spoken: browser, tunnel, API, Postgres, Ollama beside the API. Data stays home. The model sits on the home host with the API.
- The honesty cut in one example. "Dentist tomorrow at 9pm, for an hour." Parser fills due and duration. Review is editable. Apply is mine. "Schedule at" means due. A block is a different feature with a different gate.
- Two import paths, one moral. Handoff and course templates: key plus receipt. Outline: propose, review, apply, and a duplicate if you run it twice. Say the dull constraint before the pretty tree.
- The three effort numbers. 120, 20, 90. Replay does not double. Zero remaining leaves the task open. If the room is technical, add the stale revision: refresh, then decide again.
- Crew in one minute. I name the seats without an org chart. I read diffs. Renee owns what green means. Dex checks the behavior I approved. Page keeps the paper from drifting. I set the gate.
- Close on the stamp I will not give. Scheduling foundations are real and household-deployed in progress. 0.7 cutover gets a date when the records have one. Until then the honest demo is a product that can say "not effective yet" in structured output.

## Living footnote

Refresh this file at the end, before any GitHub show-and-tell. Do not treat the bullets below as status.

- [ ] **0.7 / S2 cutover.** This draft says foundations are in progress and refuses a Closed or shipped stamp. Replace that with the actual end state: what placement uses, whether S1 ever closed, what S2 did, and any push hold still open. Sources live under `docs/delivery/`. Do not copy a stamp from memory.
- [ ] **Julie.** 11/11 is the S1 CLI field test on 2026-10-12, frozen build `9d4cf48`, disposable account, Dex recorded. Confirm nothing newer superseded it. Confirm whether a real course import (the Kubernetes syllabus was planned, not claimed here) has a receipt.
- [ ] **Scale.** Rough counts at draft time: ~51k Python, ~16k TSX, ~5k TypeScript, ~4k CSS, ~77k tracked code, ~101k tracked text. Recount and date the recount.
- [ ] **Assist pin.** Operator note still says Ollama and `llama3.2`, review-before-apply, no cloud keys in the prove-it. Say so only if that is still the household setup.
- [ ] **Strip anything local.** No household hostnames, no session files, no credentials, no machine paths. If a demo needs a URL, use a placeholder.

~ Trish
