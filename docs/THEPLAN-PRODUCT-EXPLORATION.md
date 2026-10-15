<!--
==============================================================================
  File: docs/THEPLAN-PRODUCT-EXPLORATION.md
  Description: Commercialization exploration, self-hosted distribution, and optional bundled Assist.
  Component: Product Strategy
  Version: 1.2 (Exploration)
  Created: 2026-10-14
  Last Update: 2026-10-14
==============================================================================
-->

# thePlan product exploration

**Owner:** Trish. **Status:** Captured for future discovery; no implementation or commercial launch authorized. This is a product direction brief, not an addition to the current 0.7 release scope or its acceptance gates.

Explore whether thePlan should become a paid product, including a standalone, self-hosted distribution that a moderately technical person can install. Include an optional local Assist runtime so users do not need to establish their own model-hosting setup first. Preserve access for external assistants through the CLI/API.

## Why explore this now

Trish has received independent interest in the combination of practical scheduling, a less configuration-heavy experience than a project-management suite, and CLI/AI access. That is an early demand signal, not demonstrated willingness to pay.

Daily use is also starting to deliver the intended benefit. On October 14, Julie extracted three to-do items during her email scan, added them to thePlan, and reported what she had added. This is user-reported evidence of the broader workflow's value. Julie's email access and proactive behavior belong to her surrounding setup; they are not automatically capabilities supplied by thePlan or Assist.

**Positioning hypothesis:** A planner that fits work into your actual life, with tools that let your AI assistant help maintain it.

The benefit to validate is less effort maintaining the system while retaining useful scheduling, prioritization, and completion tracking.

## Direction expressed by Trish

- Investigate monetization; pricing, licensing, and business model remain undecided.
- Include a standalone version suitable for moderately technical self-hosters.
- Package the application and database with Docker containers.
- Investigate including a small language model and its runtime rather than requiring an existing local-model installation.
- Make Assist useful on its own for everyday thePlan work, including for users without an external assistant.

Here, standalone means a deployable self-hosted system with its required application services. It does not yet commit to a desktop executable, fully offline installation, or any particular supported operating system.

## Proposed distribution choices

These are Dex's recommendations for discovery, not finalized editions or pricing tiers.

| Choice | Intended experience |
| --- | --- |
| Core thePlan | Planner, scheduler, web UI, and CLI/API access without requiring an inference model. |
| Core plus local Assist | Setup provisions a supported runtime and downloads a tested small model; the user does not separately configure model hosting. |
| Existing model server | User configures a compatible endpoint and model, retaining their existing setup. |

Run bundled inference as a separate service with model weights in persistent storage. Application upgrades should not require downloading the weights again. A first-run download and an offline installation bundle are different distribution choices; offline packaging remains undecided.

Keep the model replaceable. The earlier build decision remains: retain the current Llama setup for this build and evaluate alternatives afterward.

## Current foundation and distribution work

Repository inspection on October 14 found PostgreSQL with persistent storage, API, scheduler worker, and web services in [Compose](../infra/compose/compose.yaml). Assist uses a configurable OpenAI-compatible endpoint and model; Compose currently defaults to host Ollama and `llama3.2`. This provides a starting point, not a finished customer installation package.

Discovery should cover:

- Published, versioned application images and a supported Compose package, without requiring a source build.
- First-run administrator setup, generated secrets, and removal of demo/development defaults and household-specific configuration.
- Persistent data, tested backup and restore, upgrade/migration procedures, and a documented recovery path when an upgrade fails.
- Supported operating systems, CPU/RAM/storage requirements, optional GPU profiles, and troubleshooting that a moderately technical user can follow.
- Calendar OAuth onboarding and ownership of app registrations; optional remote access and HTTPS setup.
- A dependable CLI installation and authentication path for the user and their authorized assistants.

## Assist and external assistants serve different needs

Trish expects Julie to handle most broader planning and cross-application work, including from her phone. Assist can still provide a convenient way to make a quick request while already in thePlan. Trish's own frequency of Assist use is not a proxy for its value to other users.

For someone without Julie, Dex, or another external assistant, Assist should independently support bounded everyday thePlan operations. It should ask useful clarifying questions, present understandable proposed changes, and carry out authorized actions through the same validated application operations available to other interfaces. External assistants extend the experience; they must not be prerequisites for useful in-app assistance.

Evaluate both experiences:

- **With an external assistant:** Does Assist save a trip out of the app for a quick task without creating inconsistent behavior or competing assumptions?
- **With Assist alone:** Can a user complete supported everyday planning tasks comfortably, understand the proposed result, and resolve missing information without another agent interpreting or repairing the interaction?

This is a product exploration requirement, not a claim that the expanded Assist capabilities already exist or an addition to the current 0.7 acceptance scope.

### Candidate baseline: useful everyday assistance

Define "basic" by what a person can accomplish, not by how short their request sounds. "Sort out my week" can involve substantial planning. The following is the candidate baseline for discovery and evaluation after the build; detailed acceptance cases and implementation commitments remain to be defined.

| Job | Expected experience |
| --- | --- |
| Capture work | Turn an ordinary-language request such as "Finish this report by Friday; probably two hours" into a proposed task, asking for essential missing information. |
| Maintain work | Find a task, change its estimate or deadline, record progress, mark it complete, or return it to the backlog. Clarify ambiguous task matches before changing anything. |
| Set straightforward scheduling preferences | Help express "coursework on weekday evenings" and propose the appropriate Time Map or assignment. Clarify hours and distinguish preferences from hard requirements. |
| Explain the schedule | Answer "Why is this here?" or "Why didn't this fit?" using the scheduler's actual explanations, without inventing reasons. |
| Make a bounded adjustment | Preview a supported change, explain what would move or lose time and any affected commitments, then apply the authorized change through validated application operations. |

**Acceptance standard:** A person can complete supported jobs without understanding the underlying data model, inventing CLI commands, or asking another AI to interpret or repair the result. Assist should ask sensible questions, make proposed changes understandable, and clearly explain when a request exceeds its capabilities. An unsuccessful operation must not be reported as completed.

### Outside the in-app Assist baseline

Trish agreed that the following belong outside this baseline:

- Email scanning and extracting work from other applications.
- Ongoing proactive monitoring across the user's life and work.
- Repeated-deferral coaching, including investigating estimates, avoidance, overload, or recurring time that should have been blocked.
- Broader cross-application coordination and an ongoing executive-assistant brief.

Julie is Trish's trusted executive assistant, with broader context and continuing responsibilities. Assist is an in-app helper with a bounded remit. It can be conversational, capable, and pleasant, and can flag consequences relevant to the current request, without assuming responsibility for managing the user's week. For example, it may explain that six hours of coursework will not fit the selected evenings and ask whether Saturday is an option; that does not authorize expanding availability or starting ongoing monitoring.

These boundaries describe responsibilities, not a required personality or naming convention. External assistants remain optional; the baseline above must still be useful without one.

## Bundled Assist feasibility and evaluation

Containerized inference is technically plausible: [Ollama provides a Docker image](https://registry.ollama.com/blog/ollama-is-now-available-as-an-official-docker-image), and [llama.cpp documents server containers](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md). [Compose GPU support](https://docs.docker.com/compose/how-tos/gpu-support/) depends on host hardware and configuration. These establish candidate deployment mechanisms, not acceptable thePlan performance.

Aim to evaluate a useful CPU-only baseline with optional GPU acceleration. Do not select minimum requirements from Trish's RTX 3090 experience alone. No model, quantization, memory floor, or response-time promise is selected yet.

Evaluate Assist on concrete jobs:

- Extract proposed tasks and settings from ordinary language.
- Ask for missing information instead of inventing requirements or commitments.
- Explain scheduling outcomes from application-provided facts.
- Produce structured operations that pass the application's validation and authorization boundaries.
- Recover clearly from invalid output, timeouts, and unavailable inference without blocking core planning.

The application retains scheduling calculations, hard-constraint enforcement, validation, and mutation authority. A small model's ability to fit in memory is not proof that it performs these Assist tasks reliably.

Measure correctness, clarification behavior, invalid-operation rejection, cold/warm latency, resource use, and experience on representative modest hardware. Check the exact runtime and model licenses, including commercial use and redistribution, before choosing a bundled distribution. Keep local, remote, and external-assistant data flows clear to users.

## Commercial validation before commitment

Proposed next step: a small, bounded pilot after the current version is ready. Invite interested users, observe them using their own tasks, and ask explicitly about willingness to pay.

Questions to resolve:

1. Who values the scheduling-plus-assistant-access combination enough to switch and pay?
2. What benefits work with thePlan alone, with bundled Assist, and with a user's existing assistant?
3. Can a new user install, connect accounts, recover data, and upgrade without Trish or the development crew guiding every step?
4. Does Trish want the support and operational responsibilities associated with a paid offering?
5. Which commercial model fits the audience and sustainable support effort: paid self-hosted licenses, support/updates, hosted service, or a combination? No choice is locked.

**Revisit trigger:** Trish elects to begin product/distribution discovery after the current feature work. Use this brief to prepare that discussion; do not turn it into a build queue automatically.
