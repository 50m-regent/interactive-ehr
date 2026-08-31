---
marp: true
theme: research
paginate: true
math: mathjax
title: "Research Meeting"
author: "Ren Hirata"
lang: "en"
---

<!-- _class: cover -->
<!-- _paginate: false -->

# Research Meeting

###### 2026-08-24

#### Ren Hirata

---

<!-- _class: summary -->

# Research to date

| Item | Description |
| --- | --- |
| Background | EHRs contain extensive information, while data needed for care is spread across multiple screens |
| Goal | Bring together the information required for each clinical task and support efficient review |
| Approach | Identify the required data and presentation from the task, then create a UI suited to its purpose |

---

<!-- _class: comparison -->

# Change how clinicians reach the information they need

1. Fixed screens

   Required information is spread across screens and records.

   Users must remember where it is and how to reach it.

2. Task-aligned screens

   The system gathers the data needed for the question at hand.

   Lists, tables, and trends appear together for the same clinical context.

---

<!-- _class: parallel -->

# Recent progress and CHI 2027 submission

## User evaluation

1. Discussing potential collaborators through Dr. Yabe
2. Starting after ethics and study requirements are met

## CHI 2027 Papers

1. Build evaluation data from EHRSQL, which pairs clinical questions with reference SQL
2. Detect, locate, and repair gaps across questions, SQL, query results, and screens

*The first submission will focus on technical evaluation; human-subject evaluation will follow as future validation*

---

<!-- _class: pipeline -->

# Connect tasks, data, and presentation to build the UI

1. **Clinical question**

   Organize the user's task and clinical context.

2. **Task graph**

   Connect clinical tasks, required data, and interface components.

3. **UI with data**

   Run SQL and render the results as tables or charts.

---

<!-- _class: comparison -->

# Current implementation and future generation

1. Current

   We manually create structural JSON from interviews.

   The system reads the task graph and renders the UI with rules.

2. Future

   A custom model will interpret the user's request.

   It will construct the proposed task graph and update the UI.

---

<!-- _class: labeled-sections -->

# Preoperative anesthesia scenario developed with Dr. Ito

> We organized the clinical setting and review tasks based on interviews with Dr. Ito

## Clinical setting

> Before surgery, review the patient's background and prepare anesthesia precautions and explanations

## Review tasks

- Patient background and planned surgery
- Social history and allergies
- Medical history, treatment, and laboratory results
- Anesthesia history and anesthesia risks

---

<!-- _class: visual-pair -->

# Preoperative anesthesia clinic UI

![Preoperative anesthesia clinic showing the patient information tab](assets/patient-overview.jpg)

Patient information

![Preoperative anesthesia clinic showing recent laboratory results](assets/lab-results.jpg)

Laboratory results

Synthetic data only. The patient and timestamp remain fixed while the review target changes

---

<!-- _class: pipeline -->

# Compare screens using the same DWH data

1. **Hospital DWH**

   Use the same data referenced by the operational EHR.

2. **Traceable retrieval**

   Trace displayed values to SQL, source tables, and data timestamps.

3. **UI comparison**

   Compare the current screen and proposed UI using the same data.

---

<!-- _class: parallel -->

# Planned user evaluation

## Comparison design

1. Matched synthetic cases
2. Within-participant EHR vs. UI
3. Counterbalanced order

## Measures

1. Success and critical omissions
2. Time, actions, and screen transitions
3. NASA-TLX, SUS, interviews

Begin after expert review, ethics approval, and institutional authorization

---

<!-- _class: callout -->

# Feedback requested from clinicians

> ## Review it as a clinical interface
>
> - Does it include the information needed to prevent critical omissions?
> - Are the information groups and review order natural?
> - Can the source, timestamp, and retrieval conditions support verification?
> - Are the comparison conditions with the current EHR fair?
