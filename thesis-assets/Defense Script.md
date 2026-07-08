# Opening:

Good morning, respected members of the committee, lecturers, and everyone attending my bachelor's thesis defense.

First of all, I would like to express my sincere gratitude for your time and the opportunity to present my research today.

My thesis is titled "Design and Implementation of an AI-powered Monitoring and Observability Platform for Automated Optical Inspection Systems."

*slide 1: thesis title*

Today, I will first introduce the manufacturing background, explain the problem this research addresses, present my proposed solution, demonstrate the implemented system, and finally discuss the evaluation results and future work.

*slide 2: presentation structure*

---

## Step 1: Problem

*slide 3: PCB board and electrical devices like GPU, wifi, router, ...*

Printed Circuit Boards, or PCBs, are fundamental components in almost every modern electronic device. As demand for AI hardware, consumer electronics, and automotive systems continues to grow, PCB manufacturing has become increasingly important.

One of the most widely used manufacturing processes is Surface Mount Technology, or SMT.

*slide 4: SMT images*

*point at the SMT image*

As shown in this production line, the PCB first passes through solder paste printing, followed by component placement using Pick-and-Place machines.

To ensure product quality, the boards are then inspected by Automated Optical Inspection, or AOI, systems.

*slides 5: AOI machines*

*Now point*

In this production line, two AOI machines are deployed.

The first AOI performs inspection before the reflow process to detect component placement errors.

The second AOI performs the final quality inspection after soldering has been completed.

---

## Step 2: Why Current Solutions Are Not Enough

**Now transition.**

> "So what kinds of defects can occur during PCB manufacturing?"

*slide 6: images of defections*

*(show images)*

> "Examples include missing components, misalignment, polarity errors, tombstoning, solder bridges, and insufficient solder joints."

> "Detecting these defects accurately is critical because even a single faulty component may lead to product failure."

**Then transition.**

*slide 7: table of comparision between AI-AOI and rule-based AOI in terms of efficiency*

> "Traditionally, AOI systems relied on rule-based image processing."

> "While effective in many cases, these systems often generated false positives and false negatives under complex production conditions."

**Then**

> "To improve inspection accuracy, modern production lines increasingly integrate deep learning models into AOI systems."

**Then**

> "However, introducing AI creates a new challenge."

**Pause.**

> "AI models can experience degraded confidence, abnormal prediction behavior, unexpected failures, or performance changes over time."

*slide 8: AI failure dashbooard or example of an AI problem*

**Another pause.**

> "Despite these risks, many AOI deployments primarily focus on inference accuracy while providing limited visibility into the behavior of the AI system itself."

> "Engineers often lack a centralized platform to monitor inference results, analyze abnormal events, trace prediction history, and diagnose system failures efficiently."

**Then conclude.**

> "This observation motivated the research presented in this thesis."

---

## Step 3: My proposed idea

*slide 9: architecture of the system*

> "Based on the previous problem, my proposed idea is to make the AI inference process observable without directly interrupting the AOI application."

> "Instead of only showing the final prediction result, the AOI application also produces structured inference events in JSON format."

**Then point to AOI app.**

> "Each event contains important information such as timestamp, prediction result, confidence score, latency, status, and possible error message."

**Point to log file.**

> "These events are written as append-only logs. This design keeps the inference application simple and avoids tightly coupling it to the monitoring system."

**Point to Promtail.**

> "Promtail acts as a lightweight log collector. It continuously reads the log file, attaches labels such as service name or environment, and forwards the logs to Loki."

**Point to Loki.**

> "Loki stores and indexes the logs using labels instead of indexing the full message content. This makes it lightweight and suitable for log-based monitoring."

**Point to Grafana.**

> "Finally, Grafana queries Loki and transforms these logs into operational dashboards, such as total inference events, recent failures, confidence distribution, and latency trends."

**Then conclude:**

> "In other words, the proposed system turns raw AI predictions into observable engineering signals."

*slide 10: tables of comparision between Loki, ELK, , answering question why Loki ?*

> "After designing the architecture, the next question was selecting a monitoring stack."

> "I compared three popular logging platforms."

### Loki

> "Loki was selected because it indexes labels instead of the entire log content."

> "This significantly reduces storage requirements while remaining fast for structured monitoring queries."

### ELK

> "ELK provides powerful full-text search but requires significantly more storage and operational resources."

### OpenSearch

> "OpenSearch offers capabilities similar to Elasticsearch and is fully open source, but its deployment complexity is still higher than what this project requires."

**Then finish with**

> "Since this thesis focuses on monitoring an AI inference service rather than building a large enterprise logging platform, Loki provides the best balance between simplicity, performance, and maintainability."

---

## Step 4: How it works

Let me show you one event travelling through the system by zooming into that backend and follow one inference event through the pipeline,

### Start

> "Now let us follow one PCB inspection through the system."

### Step 1

*(point to AOI)*

> "The operator uploads a PCB image."

### Step 2

> "The AI model performs defect detection."

### Step 3

> "The backend converts the prediction into a structured inference event."

**Pause.**

This is your most important sentence.

**Not**

> "The backend logs data."

**Instead**

> "The prediction becomes an operational event."

Huge difference.

### Step 4

> "The event is written into a JSON log."

### Step 5

> "Promtail automatically detects the new log entry and forwards it to Loki."

### Step 6

> "Loki stores and indexes the event."

### Step 7

> "Grafana continuously queries Loki."

### Step 8

> "The dashboard is updated almost immediately."

### Step 9

> "If abnormal behavior is detected, predefined alert rules notify engineers."

> "In other words, instead of only knowing what the AI predicted, engineers can also understand how the AI system behaves during operation."
